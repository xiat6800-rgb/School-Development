from datetime import timedelta

from flask import current_app

from app.constants import AUCTION_DURATIONS_MINUTES
from app.extensions import db
from app.models import Artwork, Auction, AutoBid, Bid, User
from app.services.common import BusinessError
from app.services.event_service import validate_event_operation
from app.services.notification_service import create_notification
from app.services.point_service import change_points, grant_bonus_points
from app.utils import utcnow


def _lock_auction(auction_id):
    auction = Auction.query.filter_by(id=auction_id).with_for_update().first()
    if not auction:
        raise BusinessError("オークションが見つかりません。")
    return auction


def _lock_user(user_id):
    user = User.query.filter_by(id=user_id).with_for_update().first()
    if not user or not user.is_active:
        raise BusinessError("利用できないアカウントです。")
    return user


def create_auction(artwork, start_price, duration_minutes, *, now=None,
                   relist=False):
    now = now or utcnow()
    validate_event_operation("listing", now)
    if isinstance(start_price, bool) or not isinstance(start_price, int):
        raise BusinessError("開始価格は0以上の整数ptで入力してください。")
    if start_price < 0 or duration_minutes not in AUCTION_DURATIONS_MINUTES:
        raise BusinessError("開始価格または開催時間が不正です。")
    ends_at = now + timedelta(minutes=duration_minutes)
    if ends_at > current_app.config["EVENT_ENDS_AT"]:
        raise BusinessError("イベント終了までに開催時間を確保できません。")
    artwork = Artwork.query.filter_by(id=artwork.id).with_for_update().first()
    if not artwork.is_saved:
        raise BusinessError("PNGとレイヤーZIPの正式保存後に出品できます。")
    if artwork.active_auction:
        raise BusinessError("同じ作品を同時に複数出品することはできません。")
    if any(a.winner_id for a in artwork.auctions):
        raise BusinessError("落札済み作品は再出品できません。")
    if relist:
        latest = artwork.latest_auction
        if not latest or not (
            latest.status == "cancelled"
            or (latest.status == "ended" and latest.winner_id is None)
        ):
            raise BusinessError("取消済み・未落札終了の作品だけ再出品できます。")
        if not artwork.is_public:
            raise BusinessError("非公開中の作品は再出品できません。")
    elif artwork.status != "draft":
        raise BusinessError("この下書きはすでに出品されています。")

    auction = Auction(
        artwork=artwork,
        start_price=start_price,
        current_price=start_price,
        starts_at=now,
        ends_at=ends_at,
        status="active",
    )
    artwork.status = "listed"
    artwork.is_public = True
    artwork.visibility_reason = None
    db.session.add(auction)
    db.session.flush()
    grant_bonus_points(artwork.artist, "first_listing", auction=auction)
    return auction


def create_relisted_auction(artwork, start_price, duration_minutes, *, now=None):
    return create_auction(
        artwork, start_price, duration_minutes, now=now, relist=True
    )


def _validate_bid(auction, bidder, amount, now, expected_price=None):
    if auction.status != "active" or now >= auction.ends_at:
        raise BusinessError("このオークションは入札受付を終了しています。")
    if bidder.id == auction.artwork.artist_id:
        raise BusinessError("自分の作品には入札できません。")
    if isinstance(amount, bool) or not isinstance(amount, int) or amount <= auction.current_price:
        raise BusinessError(f"入札額は{auction.current_price + 1:,}pt以上にしてください。")
    if expected_price is not None and expected_price != auction.current_price:
        raise BusinessError("確認後に価格が変わりました。最新価格で再度確認してください。")


def refund_bid_points(bid, *, now=None):
    """1件の未返還デビットを戻す。呼出側のTransactionに参加する。"""
    if bid.refunded_at is not None:
        return False
    now = now or utcnow()
    if bid.held_amount:
        change_points(
            bid.bidder, bid.held_amount, "refund", f"bid:{bid.id}:refund",
            auction=bid.auction, bid=bid, note="高値更新・取消による返還",
        )
    bid.refunded_at = now
    return True


def _refund_user_unreturned_bids(auction, user_id, *, now=None):
    bids = Bid.query.filter_by(
        auction_id=auction.id, bidder_id=user_id, refunded_at=None
    ).order_by(Bid.id).all()
    for bid in bids:
        refund_bid_points(bid, now=now)


def _accept_bid(auction, bidder, amount, *, is_auto=False, now=None):
    now = now or utcnow()
    previous = auction.current_bid
    previous_bidder_id = previous.bidder_id if previous else None
    same_bidder = previous_bidder_id == bidder.id
    debit = amount - auction.current_price if same_bidder else amount
    if bidder.point_balance < debit:
        raise BusinessError("ポイント残高が不足しています。")

    if previous and not same_bidder:
        previous_bidder = _lock_user(previous_bidder_id)
        _refund_user_unreturned_bids(auction, previous_bidder.id, now=now)

    bid = Bid(
        auction=auction,
        bidder=bidder,
        amount=amount,
        held_amount=debit,
        is_auto=is_auto,
    )
    db.session.add(bid)
    db.session.flush()
    change_points(
        bidder, -debit, "bid", f"bid:{bid.id}:debit",
        auction=auction, bid=bid,
        note="自動入札" if is_auto else "手動入札",
    )
    auction.current_price = amount
    auction.current_bid = bid
    db.session.flush()

    create_notification(
        auction.seller, "bid_received", "新しい入札がありました",
        f"『{auction.artwork.title}』に{amount:,}ptの入札が受理されました。",
        f"notice:bid-received:{bid.id}", auction=auction,
    )
    if previous and not same_bidder:
        create_notification(
            previous.bidder, "outbid", "最高入札が更新されました",
            f"『{auction.artwork.title}』の現在価格は{amount:,}ptです。未返還分は返還済みです。",
            f"notice:outbid:{bid.id}", auction=auction,
        )
    return bid


def place_bid(auction_id, bidder_id, amount, *, expected_price=None, now=None):
    now = now or utcnow()
    auction = _lock_auction(auction_id)
    bidder = _lock_user(bidder_id)
    _validate_bid(auction, bidder, amount, now, expected_price)
    bid = _accept_bid(auction, bidder, amount, now=now)
    process_auto_bids(auction, now=now)
    return bid


def _auto_bid_candidates(auction):
    return AutoBid.query.filter_by(
        auction_id=auction.id, is_active=True
    ).order_by(AutoBid.max_amount.desc(), AutoBid.created_at, AutoBid.id).all()


def process_auto_bids(auction, *, now=None):
    """上限と次点から必要額を求め、1pt単位の最低落札価格で競り上げる。"""
    now = now or utcnow()
    if auction.status != "active" or now >= auction.ends_at:
        return
    # 残高不足の設定を停止した場合だけ、最大設定件数分やり直す。
    for _ in range(100):
        price = auction.current_price
        current_user_id = auction.current_bid.bidder_id if auction.current_bid else None
        candidates = [c for c in _auto_bid_candidates(auction) if c.max_amount > price]
        if not candidates:
            return
        candidate = candidates[0]
        opponents = [c for c in candidates[1:] if c.user_id != candidate.user_id]
        if candidate.user_id == current_user_id and not opponents:
            return
        opposing_limit = max((c.max_amount for c in opponents), default=price)
        target = min(candidate.max_amount, max(price + 1, opposing_limit + 1))
        if target <= price:
            return
        bidder = _lock_user(candidate.user_id)
        required = target - price if bidder.id == current_user_id else target
        if bidder.point_balance < required:
            candidate.is_active = False
            create_notification(
                bidder, "auto_bid_stopped", "自動入札を停止しました",
                f"『{auction.artwork.title}』は残高不足のため自動入札を停止しました。",
                f"notice:auto-insufficient:{candidate.id}:{candidate.updated_at.timestamp()}",
                auction=auction,
            )
            db.session.flush()
            continue
        _accept_bid(auction, bidder, target, is_auto=True, now=now)
        db.session.flush()
    raise BusinessError("自動入札の処理が上限を超えました。時間をおいて再確認してください。")


def configure_auto_bid(auction_id, user_id, max_amount, *, now=None):
    now = now or utcnow()
    auction = _lock_auction(auction_id)
    user = _lock_user(user_id)
    if auction.status != "active" or now >= auction.ends_at:
        raise BusinessError("終了したオークションには設定できません。")
    if auction.artwork.artist_id == user.id:
        raise BusinessError("自分の作品には自動入札を設定できません。")
    if isinstance(max_amount, bool) or not isinstance(max_amount, int) or max_amount < 0:
        raise BusinessError("上限額は0以上の整数ptで入力してください。")
    own_accepted = (
        auction.current_price
        if auction.current_bid and auction.current_bid.bidder_id == user.id else 0
    )
    if max_amount < own_accepted:
        raise BusinessError("受理済みの入札額より低い上限には変更できません。")
    next_price = auction.current_price + 1
    required = next_price - own_accepted if own_accepted else next_price
    if user.point_balance < required:
        raise BusinessError("次の入札に必要なポイント残高がありません。")
    setting = AutoBid.query.filter_by(auction_id=auction.id, user_id=user.id).first()
    if setting:
        setting.max_amount = max_amount
        setting.is_active = True
        setting.updated_at = now
    else:
        setting = AutoBid(
            auction=auction, user=user, max_amount=max_amount, is_active=True
        )
        db.session.add(setting)
    db.session.flush()
    process_auto_bids(auction, now=now)
    return setting


def stop_auto_bid(auction_id, user_id):
    setting = AutoBid.query.filter_by(auction_id=auction_id, user_id=user_id).first()
    if setting:
        setting.is_active = False
    return setting


def close_auction(auction_id, *, now=None):
    now = now or utcnow()
    auction = _lock_auction(auction_id)
    if auction.status != "active":
        return auction, False
    if now < auction.ends_at:
        raise BusinessError("終了日時前のオークションは確定できません。")
    for setting in auction.auto_bids:
        setting.is_active = False
    winning_bid = auction.current_bid
    auction.status = "ended"
    auction.settled_at = now
    if winning_bid:
        auction.winner_id = winning_bid.bidder_id
        auction.winner_bid_id = winning_bid.id
        auction.final_price = winning_bid.amount
        auction.artwork.status = "sold"
        seller = _lock_user(auction.artwork.artist_id)
        change_points(
            seller, winning_bid.amount, "sale", f"auction:{auction.id}:sale",
            auction=auction, bid=winning_bid, note="落札代金（手数料なし）",
        )
        create_notification(
            winning_bid.bidder, "auction_won", "落札が確定しました",
            f"『{auction.artwork.title}』を{winning_bid.amount:,}ptで落札しました。原寸PNGとZIPを取得できます。",
            f"notice:won:{auction.id}", auction=auction,
        )
        create_notification(
            seller, "auction_sold", "作品が落札されました",
            f"『{auction.artwork.title}』の落札額{winning_bid.amount:,}ptを残高へ加算しました。",
            f"notice:sold:{auction.id}", auction=auction,
        )
    else:
        auction.final_price = None
        auction.artwork.status = "unsold"
        create_notification(
            auction.seller, "auction_unsold", "オークションが終了しました",
            f"『{auction.artwork.title}』は入札がなく未落札で終了しました。再出品できます。",
            f"notice:unsold:{auction.id}", auction=auction,
        )
    db.session.flush()
    return auction, True


def close_expired_auctions(*, now=None):
    now = now or utcnow()
    auctions = Auction.query.filter(
        Auction.status == "active", Auction.ends_at <= now
    ).order_by(Auction.ends_at).all()
    closed = 0
    for auction in auctions:
        _, changed = close_auction(auction.id, now=now)
        closed += int(changed)
    db.session.flush()
    return closed
