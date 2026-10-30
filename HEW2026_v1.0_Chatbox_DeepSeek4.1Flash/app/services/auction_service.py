"""出品・入札・返還・落札確定・自動入札。"""

from datetime import timedelta

from flask import current_app

from ..clock import utcnow
from ..constants import (
    ARTWORK_STATUS_DRAFT,
    ARTWORK_STATUS_LISTED,
    ARTWORK_STATUS_SOLD,
    ARTWORK_VISIBILITY_PUBLIC,
    AUCTION_CLOSED_TIME_EXPIRED,
    AUCTION_STATUS_ACTIVE,
    AUCTION_STATUS_ENDED,
    BID_STATUS_ACCEPTED,
    BONUS_FIRST_LISTING,
    EVENT_OPERATION_LIST,
    NOTIFICATION_AUCTION_UNSOLD,
    NOTIFICATION_AUCTION_WON,
    NOTIFICATION_AUTO_BID_STOPPED,
    NOTIFICATION_BID_RECEIVED,
    NOTIFICATION_OUTBID,
    WALLET_TYPE_BID,
    WALLET_TYPE_PURCHASE,
    WALLET_TYPE_REFUND,
)
from ..extensions import db
from ..models import Artwork, Auction, AutoBidSetting, Bid, User, WalletTransaction
from . import event_service, notification_service, point_service, tag_service
from .errors import (
    BidError,
    InsufficientPointsError,
    PriceChangedError,
    ValidationError,
)


# --------------------------------------------------------------------------
# 取得系
# --------------------------------------------------------------------------


def get_auction(auction_id):
    return db.session.get(Auction, int(auction_id))


def get_current_top_bid(auction):
    """現時点の最高額（受理済み）の入札を返す。"""
    return db.session.scalar(
        db.select(Bid)
        .where(
            Bid.auction_id == auction.id,
            Bid.bid_status == BID_STATUS_ACCEPTED,
        )
        .order_by(Bid.bid_amount.desc(), Bid.id.desc())
        .limit(1)
    )


def list_accepted_bids(auction_id, limit=30):
    """入札履歴を新しい順に取得する。"""
    return db.session.scalars(
        db.select(Bid)
        .where(
            Bid.auction_id == auction_id,
            Bid.bid_status == BID_STATUS_ACCEPTED,
        )
        .order_by(Bid.id.desc())
        .limit(limit)
    ).all()


def list_active_auctions(limit=24):
    """開催中の競売を終了が近い順に取得する。"""
    return db.session.scalars(
        db.select(Auction)
        .where(Auction.status == AUCTION_STATUS_ACTIVE)
        .order_by(Auction.end_time)
        .limit(limit)
    ).all()


def list_public_artworks(limit=24):
    """公開作品を新しい順に取得する。"""
    return db.session.scalars(
        db.select(Artwork)
        .where(
            Artwork.status.in_((ARTWORK_STATUS_LISTED, ARTWORK_STATUS_SOLD)),
            Artwork.visibility == ARTWORK_VISIBILITY_PUBLIC,
        )
        .order_by(Artwork.created_at.desc())
        .limit(limit)
    ).all()


def list_user_auctions(user_id, limit=20):
    """本人が出品した競売を新しい順に取得する。"""
    return db.session.scalars(
        db.select(Auction)
        .join(Artwork, Auction.artwork_id == Artwork.id)
        .where(Artwork.artist_id == user_id)
        .order_by(Auction.created_at.desc())
        .limit(limit)
    ).all()


def get_auto_bid_setting(auction_id, user_id):
    return db.session.scalar(
        db.select(AutoBidSetting).where(
            AutoBidSetting.auction_id == auction_id,
            AutoBidSetting.user_id == user_id,
        )
    )


def list_active_auto_bid_settings(auction_id):
    return db.session.scalars(
        db.select(AutoBidSetting).where(
            AutoBidSetting.auction_id == auction_id,
            AutoBidSetting.is_active.is_(True),
        )
    ).all()


# --------------------------------------------------------------------------
# 内部ヘルパー
# --------------------------------------------------------------------------


def _lock(model, identifier):
    """行ロックを取得する。SQLite では FOR UPDATE は無視される。"""
    return db.session.execute(
        db.select(model).where(model.id == identifier).with_for_update()
    ).scalar_one_or_none()


def _as_points(value, label="ポイント"):
    try:
        amount = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValidationError(f"{label}は整数で入力してください。")
    if amount < 0:
        raise ValidationError(f"{label}は 0 以上で入力してください。")
    return amount


# --------------------------------------------------------------------------
# 出品
# --------------------------------------------------------------------------


def create_auction(
    seller,
    artwork_id,
    title,
    description,
    start_price,
    duration_minutes,
    tag_ids=None,
    now=None,
):
    """下書きを公開し、競売を開始する。"""
    now = now or utcnow()
    config = current_app.config
    event_service.validate_event_operation(EVENT_OPERATION_LIST, now)

    artwork = _lock(Artwork, int(artwork_id))
    if artwork is None or not artwork.is_owned_by(seller):
        raise ValidationError("出品できるのは自分の下書きだけです。")
    if artwork.auction is not None:
        raise ValidationError("この作品はすでに出品されています。")
    if artwork.status != ARTWORK_STATUS_DRAFT:
        raise ValidationError("下書きの作品だけ出品できます。")
    if not artwork.is_saved:
        raise ValidationError("PNG とレイヤー ZIP の正式保存が完了していません。")

    price = _as_points(start_price, "開始価格")
    try:
        minutes = int(duration_minutes)
    except (TypeError, ValueError):
        raise ValidationError("開催時間を選択してください。")
    if minutes not in config["AUCTION_DURATIONS"]:
        raise ValidationError("開催時間は5・10・15・20分から選択してください。")

    title = (title or "").strip()
    if not title:
        raise ValidationError("タイトルを入力してください。")
    if len(title) > 200:
        raise ValidationError("タイトルは200文字以内で入力してください。")

    end_time = now + timedelta(minutes=minutes)
    event_end = config.get("EVENT_ENDS_AT")
    if event_end and end_time > event_end:
        raise ValidationError(
            "イベント終了までに開催時間を確保できません。"
            "より短い開催時間を選んでください。"
        )

    artwork.title = title
    artwork.description = (description or "").strip()[:2000] or None
    artwork.status = ARTWORK_STATUS_LISTED
    tag_service.set_artwork_tags(artwork, tag_ids)

    auction = Auction(
        artwork_id=artwork.id,
        start_price=price,
        current_price=price,
        status=AUCTION_STATUS_ACTIVE,
        start_time=now,
        end_time=end_time,
    )
    db.session.add(auction)
    db.session.flush()

    # 初出品ボーナス（1 アカウント 1 回・再送しても重複しない）
    point_service.grant_bonus_points(seller, BONUS_FIRST_LISTING, now)
    db.session.commit()
    return auction


# --------------------------------------------------------------------------
# 入札
# --------------------------------------------------------------------------


def place_bid(
    auction_id,
    bidder_id,
    bid_amount,
    expected_current_price=None,
    is_auto_bid=False,
    run_auto_bids=True,
    now=None,
):
    """入札を受理し、消費・返還・履歴・現在価格を同一トランザクションで更新する。"""
    now = now or utcnow()
    auction = _lock(Auction, int(auction_id))
    if auction is None:
        raise BidError("オークションが見つかりません。")
    bidder = _lock(User, int(bidder_id))
    if bidder is None:
        raise BidError("入札する利用者が見つかりません。")

    top_bid = get_current_top_bid(auction)
    amount = _as_points(bid_amount, "入札額")
    _validate_bid(auction, bidder, amount, top_bid, expected_current_price, now)
    bid = _apply_bid(auction, bidder, amount, top_bid, is_auto_bid, now)
    db.session.commit()

    if run_auto_bids:
        process_auto_bids(auction.id, now=now)
    return bid


def _validate_bid(auction, bidder, amount, top_bid, expected_current_price, now):
    """ロック取得後の最新状態に対して入札条件を検証する。"""
    if not auction.is_active:
        raise BidError("このオークションは終了しています。")
    if now >= auction.end_time:
        raise BidError("終了日時を過ぎているため入札できません。")
    if auction.seller_id == bidder.id:
        raise BidError("出品者本人は入札できません。")
    if expected_current_price is not None:
        try:
            expected = int(str(expected_current_price).strip())
        except (TypeError, ValueError):
            raise PriceChangedError("現在価格を確認してから入札してください。")
        if expected != auction.current_price:
            raise PriceChangedError(
                "現在価格が更新されました。最新の価格を確認してください。"
            )
    if amount < auction.current_price + 1:
        raise BidError("入札額は現在価格より 1pt 以上高い金額にしてください。")

    already_committed = (
        top_bid.bid_amount
        if top_bid is not None and top_bid.bidder_id == bidder.id
        else 0
    )
    if amount - already_committed > bidder.point_balance:
        raise InsufficientPointsError("ポイント残高が不足しています。")


def _apply_bid(auction, bidder, amount, top_bid, is_auto_bid, now):
    """入札行・残高・履歴・通知を同一トランザクション内で更新する。"""
    already_committed = (
        top_bid.bid_amount
        if top_bid is not None and top_bid.bidder_id == bidder.id
        else 0
    )
    charge = amount - already_committed
    if charge > 0:
        point_service.add_points(
            bidder,
            -charge,
            WALLET_TYPE_BID,
            related_auction_id=auction.id,
            memo="入札",
        )

    bid = Bid(
        auction_id=auction.id,
        bidder_id=bidder.id,
        bid_amount=amount,
        is_auto_bid=is_auto_bid,
        bid_status=BID_STATUS_ACCEPTED,
        created_at=now,
    )
    db.session.add(bid)
    db.session.flush()

    auction.current_price = amount

    if top_bid is not None and top_bid.bidder_id != bidder.id:
        refund_bid_points(top_bid, auction)

    artwork_title = auction.artwork.title if auction.artwork else "作品"
    notification_service.create_notification(
        auction.seller_id,
        NOTIFICATION_BID_RECEIVED,
        "入札がありました",
        f"「{artwork_title}」に {amount:,}pt の入札が入りました。",
        related_auction_id=auction.id,
        related_bid_id=bid.id,
    )
    if top_bid is not None and top_bid.bidder_id != bidder.id:
        notification_service.create_notification(
            top_bid.bidder_id,
            NOTIFICATION_OUTBID,
            "高値更新されました",
            f"「{artwork_title}」で他の利用者に高値を更新されました。",
            related_auction_id=auction.id,
            related_bid_id=bid.id,
        )
    return bid


def refund_bid_points(bid, auction=None):
    """高値更新で前最高入札者の未返還ポイントを返還する。

    返還済みの入札は二重に返さない。呼び出し元のトランザクションに参加する。
    """
    auction_id = auction.id if auction is not None else bid.auction_id
    refunded = db.session.scalar(
        db.select(db.func.count(WalletTransaction.id)).where(
            WalletTransaction.related_bid_id == bid.id,
            WalletTransaction.transaction_type == WALLET_TYPE_REFUND,
        )
    )
    if refunded:
        return None
    bidder = db.session.get(User, bid.bidder_id)
    if bidder is None:
        return None
    return point_service.add_points(
        bidder,
        bid.bid_amount,
        WALLET_TYPE_REFUND,
        related_auction_id=auction_id,
        related_bid_id=bid.id,
        memo="高値更新による返還",
    )


# --------------------------------------------------------------------------
# 自動入札
# --------------------------------------------------------------------------


def configure_auto_bid(auction_id, user_id, max_amount, now=None):
    """自動入札の上限額を設定・変更し、直後に判定する。"""
    now = now or utcnow()
    auction = _lock(Auction, int(auction_id))
    user = _lock(User, int(user_id))
    if auction is None or user is None:
        raise BidError("オークションまたは利用者が見つかりません。")
    if not auction.is_active or now >= auction.end_time:
        raise BidError("終了したオークションには自動入札を設定できません。")
    if auction.seller_id == user.id:
        raise BidError("出品者本人は自動入札を設定できません。")

    limit = _as_points(max_amount, "上限額")
    if limit < auction.current_price + 1:
        raise BidError("上限額は現在価格より 1pt 以上高い金額にしてください。")

    top_bid = get_current_top_bid(auction)
    setting = get_auto_bid_setting(auction.id, user.id)
    if (
        setting is not None
        and top_bid is not None
        and top_bid.bidder_id == user.id
        and limit < top_bid.bid_amount
    ):
        raise BidError("上限額は自分の受理済み入札額より低くできません。")

    committed = (
        top_bid.bid_amount
        if top_bid is not None and top_bid.bidder_id == user.id
        else 0
    )
    required = min(limit, auction.current_price + 1) - committed
    if required > 0 and user.point_balance < required:
        raise InsufficientPointsError(
            "自動入札に必要なポイント残高が不足しています。"
        )

    if setting is None:
        setting = AutoBidSetting(
            auction_id=auction.id,
            user_id=user.id,
            max_amount=limit,
            created_at=now,
        )
        db.session.add(setting)
    else:
        # 上限変更・再開。受理済み入札は維持する。
        setting.max_amount = limit
        setting.is_active = True
    db.session.commit()

    process_auto_bids(auction.id, now=now)
    return get_auto_bid_setting(auction.id, user.id)


def stop_auto_bid(auction_id, user_id):
    """本人の自動入札を停止する。受理済み入札は取り消さない。"""
    setting = get_auto_bid_setting(int(auction_id), int(user_id))
    if setting is None:
        raise ValidationError("自動入札の設定がありません。")
    setting.is_active = False
    db.session.commit()
    return setting


def _select_auto_bid_candidate(auction, settings, top_bid, now):
    """上限額と設定日時から次の入札候補を選ぶ。

    出品者本人・現在の最高入札者は除外する。同額上限なら設定日時が早い順。
    """
    seller_id = auction.seller_id
    top_bidder_id = top_bid.bidder_id if top_bid is not None else None
    candidates = [
        setting
        for setting in settings
        if setting.is_active
        and setting.user_id != seller_id
        and setting.user_id != top_bidder_id
        and setting.max_amount >= auction.current_price + 1
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item.max_amount, item.created_at, item.id))
    return candidates[0]


def _next_auto_bid_amount(auction, candidate, settings, top_bid):
    """上限内で勝つために必要な額だけを 1pt 単位で算出する。

    上限額が同額でも設定日時が早ければ勝てるため、同額の相手には
    同額まで、下位の上限の相手には +1pt まで競り上げる。
    """
    floor_price = auction.current_price
    if top_bid is not None:
        floor_price = max(floor_price, top_bid.bid_amount)

    others = [
        setting
        for setting in settings
        if setting.is_active and setting.user_id != candidate.user_id
    ]
    if others:
        second = max(
            others,
            key=lambda item: (item.max_amount, -item.created_at.timestamp()),
        )
        needed = (
            second.max_amount
            if second.max_amount >= candidate.max_amount
            else second.max_amount + 1
        )
        target = max(floor_price + 1, needed)
    else:
        target = floor_price + 1

    return min(candidate.max_amount, target)


def process_auto_bids(auction_id, now=None):
    """他者の入札に応じて、上限額の範囲で自動的に競り上げる。

    残高不足なら該当の自動入札を停止して本人へ通知する。
    再帰呼び出しによる無限実行を避けるためループで処理する。
    """
    now = now or utcnow()
    max_rounds = current_app.config.get("MAX_AUTO_BID_ROUNDS", 50)
    accepted = 0

    for _ in range(max_rounds):
        auction = _lock(Auction, int(auction_id))
        if auction is None or not auction.is_active or now >= auction.end_time:
            break
        settings = list_active_auto_bid_settings(auction.id)
        if not settings:
            break
        top_bid = get_current_top_bid(auction)
        candidate = _select_auto_bid_candidate(auction, settings, top_bid, now)
        if candidate is None:
            break

        amount = _next_auto_bid_amount(auction, candidate, settings, top_bid)
        if amount is None or amount <= auction.current_price:
            break

        bidder = db.session.get(User, candidate.user_id)
        if bidder is None:
            candidate.is_active = False
            db.session.commit()
            continue

        committed = (
            top_bid.bid_amount
            if top_bid is not None and top_bid.bidder_id == bidder.id
            else 0
        )
        if amount - committed > bidder.point_balance:
            candidate.is_active = False
            notification_service.create_notification(
                bidder.id,
                NOTIFICATION_AUTO_BID_STOPPED,
                "自動入札を停止しました",
                "ポイント残高が不足したため、自動入札を停止しました。",
                related_auction_id=auction.id,
                dedupe_key=f"auto-stop:{candidate.id}",
            )
            db.session.commit()
            continue

        _apply_bid(auction, bidder, amount, top_bid, True, now)
        db.session.commit()
        accepted += 1

    return accepted


# --------------------------------------------------------------------------
# 終了・落札確定
# --------------------------------------------------------------------------


def close_auction(auction_id, now=None):
    """期限到達済みの 1 件を確定する。再実行しても二重処理しない。"""
    now = now or utcnow()
    auction = _lock(Auction, int(auction_id))
    if auction is None:
        return False
    if not auction.is_active:
        return False
    if now < auction.end_time:
        return False

    top_bid = get_current_top_bid(auction)
    artwork_title = auction.artwork.title if auction.artwork else "作品"
    auction.closed_at = now
    auction.closed_reason = AUCTION_CLOSED_TIME_EXPIRED

    if top_bid is None:
        auction.status = AUCTION_STATUS_ENDED
        notification_service.create_notification(
            auction.seller_id,
            NOTIFICATION_AUCTION_UNSOLD,
            "入札がないまま終了しました",
            f"「{artwork_title}」は入札がないまま終了しました。",
            related_auction_id=auction.id,
            dedupe_key=f"unsold:{auction.id}",
        )
        db.session.commit()
        return True

    auction.status = AUCTION_STATUS_ENDED
    auction.winner_id = top_bid.bidder_id
    auction.winner_bid_id = top_bid.id
    auction.final_price = top_bid.bid_amount
    if auction.artwork is not None:
        auction.artwork.status = ARTWORK_STATUS_SOLD

    # 落札額は入札時に差し引いているため、確定時に再び差し引かない。
    point_service.add_points(
        auction.artwork.artist,
        top_bid.bid_amount,
        WALLET_TYPE_PURCHASE,
        related_auction_id=auction.id,
        related_bid_id=top_bid.id,
        memo="落札代金（手数料なし）",
    )
    notification_service.create_notification(
        top_bid.bidder_id,
        NOTIFICATION_AUCTION_WON,
        "落札しました",
        f"「{artwork_title}」を {top_bid.bid_amount:,}pt で落札しました。",
        related_auction_id=auction.id,
        related_bid_id=top_bid.id,
        dedupe_key=f"won:user:{auction.id}",
    )
    notification_service.create_notification(
        auction.seller_id,
        NOTIFICATION_AUCTION_WON,
        "落札されました",
        f"「{artwork_title}」が {top_bid.bid_amount:,}pt で落札されました。",
        related_auction_id=auction.id,
        related_bid_id=top_bid.id,
        dedupe_key=f"won:seller:{auction.id}",
    )
    db.session.commit()
    return True


def close_expired_auctions(now=None, limit=100):
    """終了対象を抽出して確定処理を実行する。"""
    now = now or utcnow()
    auction_ids = db.session.scalars(
        db.select(Auction.id)
        .where(
            Auction.status == AUCTION_STATUS_ACTIVE,
            Auction.end_time <= now,
        )
        .order_by(Auction.end_time)
        .limit(limit)
    ).all()

    closed = 0
    for auction_id in auction_ids:
        try:
            if close_auction(auction_id, now=now):
                closed += 1
        except Exception:  # noqa: BLE001 - 1 件の失敗で全体を止めない
            db.session.rollback()
            current_app.logger.exception("close_auction failed: %s", auction_id)
    return closed
