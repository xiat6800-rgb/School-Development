"""オークションサービス。出品・入札・自動入札・返却・落札確定を担当する。

入札処理は対象オークション行をロックし、残高・入札履歴・ポイント取引
履歴・現在価格を同一トランザクションで更新する（要件定義書 5.4・7.3）。
"""
from datetime import datetime, timedelta, timezone

from flask import current_app

from ..extensions import db
from ..models.auction import Auction
from ..models.auto_bid import AutoBidSetting
from ..models.bid import Bid
from . import event_service, notification_service, point_service, tag_service


class AuctionError(Exception):
    """出品・入札が業務ルールに反する場合に発生する。"""


class InsufficientPointsError(AuctionError):
    """残高不足。"""


class PriceChangedError(AuctionError):
    """手動入札確認後に価格が変わった場合に発生する（再確認が必要）。"""

    def __init__(self, current_price):
        super().__init__("現在価格が変動しました。最新価格で再確認してください。")
        self.current_price = current_price


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _lock_auction(auction_id):
    auction = (
        db.session.query(Auction)
        .filter_by(id=auction_id)
        .with_for_update()
        .first()
    )
    if auction is None:
        raise AuctionError("オークションが見つかりません。")
    return auction


# ---------------------------------------------------------------- 出品


def create_auction(artwork, seller, title, description, tag_ids,
                   start_price, duration_minutes):
    """下書きを公開し、競売を即時開始する（要件定義書 5.3）。"""
    if artwork.artist_id != seller.id:
        raise AuctionError("作者本人だけが出品できます。")
    if not artwork.is_saved:
        raise AuctionError("正式保存が完了した下書きだけを出品できます。")
    if artwork.status != "draft":
        raise AuctionError("この作品は既に出品済みか出品できません。")
    if start_price < 0 or int(start_price) != start_price:
        raise AuctionError("開始価格は 0 以上の整数 pt で指定してください。")
    allowed = current_app.config["ALLOWED_AUCTION_MINUTES"]
    if duration_minutes not in allowed:
        raise AuctionError("開催時間は 5・10・15・20 分から選んでください。")
    event_service.validate_event_operation("出品")
    event_service.ensure_auction_duration(duration_minutes)

    existing = Auction.query.filter_by(artwork_id=artwork.id).first()
    if existing:
        raise AuctionError("1作品につきオークションは最大1件です（Ver0.5は再出品なし）。")

    artwork.title = (title or "").strip()
    if not artwork.title:
        raise AuctionError("タイトルを入力してください。")
    artwork.description = description
    tag_service.set_artwork_tags(artwork, tag_ids)
    artwork.status = "listed"

    now = utcnow()
    auction = Auction(
        artwork_id=artwork.id,
        start_price=start_price,
        current_price=start_price,
        status="active",
        start_time=now,
        end_time=now + timedelta(minutes=duration_minutes),
    )
    db.session.add(auction)
    db.session.flush()

    point_service.grant_bonus_points(
        seller, "first_listing", f"first_listing:{seller.id}"
    )
    db.session.commit()
    return auction


# ---------------------------------------------------------------- 入札


def _validate_bid(auction, bidder, amount, now):
    """ロック取得後の最新状態に対して入札条件を検証する内部関数。"""
    if auction.status != "active":
        raise AuctionError("このオークションは入札を受け付けていません。")
    if now >= auction.end_time:
        raise AuctionError("終了日時を過ぎたため入札できません。")
    if auction.artwork.artist_id == bidder.id:
        raise AuctionError("出品者本人は入札できません。")
    if int(amount) != amount:
        raise AuctionError("入札額は整数 pt で指定してください。")
    if amount <= auction.current_price:
        raise AuctionError(
            f"入札額は現在価格（{auction.current_price}pt）より大きくしてください。"
        )


def place_bid(auction_id, bidder, amount, is_auto_bid=False, expected_price=None):
    """入札を確定する。消費・返却・履歴・現在価格を同一トランザクションで更新。

    最高入札者自身の増額は差額だけ消費する。別ユーザーの高値更新時は
    前最高入札者に入札額を返却する。
    """
    auction = _lock_auction(auction_id)
    now = utcnow()
    if expected_price is not None and expected_price != auction.current_price:
        raise PriceChangedError(auction.current_price)
    _validate_bid(auction, bidder, amount, now)

    prev_bid = auction.highest_bid
    prev_bidder_id = prev_bid.bidder_id if prev_bid else None

    if prev_bidder_id == bidder.id:
        consume = amount - auction.current_price
    else:
        consume = amount
    if bidder.point_balance < consume:
        raise InsufficientPointsError("ポイント残高が不足しています。")

    bidder.point_balance -= consume
    bid = Bid(
        auction_id=auction.id,
        bidder_id=bidder.id,
        bid_amount=amount,
        is_auto_bid=is_auto_bid,
        bid_status="accepted",
    )
    db.session.add(bid)
    db.session.flush()
    db.session.add(
        _tx(bidder, "bid", -consume, auction.id, bid.id)
    )

    if prev_bid is not None and prev_bidder_id != bidder.id:
        refund_bid_points(auction, prev_bid)

    auction.current_price = amount
    auction.highest_bid_id = bid.id

    notification_service.create_notification(
        auction.artwork.artist_id,
        "bid_received",
        "入札がありました",
        f"「{auction.artwork.title}」に {amount}pt の入札がありました。",
        related_auction_id=auction.id,
        related_bid_id=bid.id,
    )
    db.session.commit()
    return bid


def refund_bid_points(auction, prev_bid):
    """高値更新で前最高入札者の未返還ポイントを返還する。

    呼び出し元のトランザクションに参加し、独立してコミットしない。
    """
    from ..models.user import User

    prev_bidder = db.session.get(User, prev_bid.bidder_id)
    prev_bidder.point_balance += prev_bid.bid_amount
    db.session.add(
        _tx(prev_bidder, "refund", prev_bid.bid_amount, auction.id, prev_bid.id)
    )
    notification_service.create_notification(
        prev_bidder.id,
        "outbid",
        "高値更新されました",
        f"「{auction.artwork.title}」で他のユーザーが入札しました。"
        f"{prev_bid.bid_amount}pt を返却しました。",
        related_auction_id=auction.id,
        related_bid_id=prev_bid.id,
    )


def _tx(user, tx_type, amount, auction_id=None, bid_id=None):
    from ..models.point import WalletTransaction

    return WalletTransaction(
        user_id=user.id,
        transaction_type=tx_type,
        amount=amount,
        balance_after=user.point_balance,
        related_auction_id=auction_id,
        related_bid_id=bid_id,
    )


# ---------------------------------------------------------------- 自動入札


def configure_auto_bid(auction_id, user, max_amount):
    """上限額を設定・変更し、設定直後に判定する（要件定義書 5.5）。"""
    auction = _lock_auction(auction_id)
    now = utcnow()
    if auction.status != "active" or now >= auction.end_time:
        raise AuctionError("開催中のオークションにだけ自動入札を設定できます。")
    if auction.artwork.artist_id == user.id:
        raise AuctionError("出品者本人は自動入札を設定できません。")
    if max_amount <= 0 or int(max_amount) != max_amount:
        raise AuctionError("上限額は正の整数 pt で指定してください。")

    setting = AutoBidSetting.query.filter_by(
        auction_id=auction.id, user_id=user.id
    ).first()

    own_top = _own_accepted_bid(auction, user)
    is_highest = own_top is not None and own_top.id == auction.highest_bid_id
    if own_top and max_amount < own_top.bid_amount:
        raise AuctionError("受理済み入札額より低い上限へは変更できません。")

    # 次の入札額を支払える残高を必須とする（最高入札者は差額）。
    # 上限額自体は残高を超えてよい。
    if is_highest:
        required = 1
    else:
        if max_amount <= auction.current_price:
            raise AuctionError(
                f"上限額は現在価格（{auction.current_price}pt）より大きくしてください。"
            )
        required = auction.current_price + 1
    if user.point_balance < required:
        raise InsufficientPointsError("次の入札に必要なポイント残高が不足しています。")

    if setting is None:
        setting = AutoBidSetting(
            auction_id=auction.id, user_id=user.id, max_amount=max_amount
        )
        db.session.add(setting)
    else:
        setting.max_amount = max_amount
        setting.is_active = True
    db.session.commit()

    process_auto_bids(auction.id)
    return setting


def _own_accepted_bid(auction, user):
    return (
        Bid.query.filter_by(
            auction_id=auction.id, bidder_id=user.id, bid_status="accepted"
        )
        .order_by(Bid.bid_amount.desc())
        .first()
    )


def stop_auto_bid(auction_id, user):
    """本人の設定を停止する。受理済み入札は取り消さない。"""
    setting = AutoBidSetting.query.filter_by(
        auction_id=auction_id, user_id=user.id
    ).first()
    if setting is None:
        raise AuctionError("自動入札の設定がありません。")
    setting.is_active = False
    db.session.commit()
    return setting


def _select_auto_bid_candidate(auction):
    """上限額と設定日時から次の入札候補を選ぶ内部関数。

    有効な自動入札設定（出品者を除く）と現在の最高入札を参加者として、
    上限額の降順・同額なら設定日時が早い順に並べる。
    """
    seller_id = auction.artwork.artist_id
    settings = (
        AutoBidSetting.query.filter_by(auction_id=auction.id, is_active=True)
        .filter(AutoBidSetting.user_id != seller_id)
        .all()
    )
    participants = [
        (setting.max_amount, setting.created_at, setting.user_id, setting)
        for setting in settings
    ]
    top = auction.highest_bid
    if top is not None and all(p[2] != top.bidder_id for p in participants):
        # 自動入札設定を持たない現在の最高入札者も参加者として扱う
        participants.append((top.bid_amount, top.created_at, top.bidder_id, None))
    participants.sort(key=lambda p: (-p[0], p[1]))
    return participants


def process_auto_bids(auction_id):
    """他者の入札に応じて上限額の範囲で競り上げる。

    勝つために必要な額だけを入札し、同額上限は設定日時が早い方を優先する。
    再帰呼び出しはせず、状態が収束するまで反復する。
    """
    from ..models.user import User

    guard = 0
    while True:
        guard += 1
        if guard > 200:  # 想定外の無限ループ防止
            break
        auction = _lock_auction(auction_id)
        if auction.status != "active" or utcnow() >= auction.end_time:
            db.session.commit()
            return
        participants = _select_auto_bid_candidate(auction)
        if not participants:
            db.session.commit()
            return
        winner_max, _, winner_id, winner_setting = participants[0]
        runner_up_max = participants[1][0] if len(participants) > 1 else None
        top = auction.highest_bid
        top_bidder_id = top.bidder_id if top else None
        needed = auction.current_price + 1

        if winner_id == top_bidder_id:
            # 既に最高入札者: 次点の上限が必要なところまで差額だけ競り上げる
            if runner_up_max is None:
                db.session.commit()
                return
            amount = min(winner_max, runner_up_max + 1)
            if amount <= auction.current_price:
                db.session.commit()
                return
            consume = amount - auction.current_price
        else:
            if winner_max < needed:
                db.session.commit()
                return
            amount = needed
            if runner_up_max is not None:
                amount = max(min(winner_max, runner_up_max + 1), needed)
            consume = amount

        user = db.session.get(User, winner_id)
        if user.point_balance < consume:
            # 実行時の残高不足は自動入札を停止し、本人に通知する
            if winner_setting is not None:
                winner_setting.is_active = False
                notification_service.create_notification(
                    user.id,
                    "auto_bid_stopped",
                    "自動入札を停止しました",
                    f"「{auction.artwork.title}」の自動入札は残高不足のため停止しました。",
                    related_auction_id=auction.id,
                )
                db.session.commit()
                continue
            db.session.commit()
            return
        place_bid(auction.id, user, amount, is_auto_bid=True)


# ---------------------------------------------------------------- 終了・落札


def close_auction(auction_id):
    """期限到達済みの1件を確定する。再実行でも二重処理しない。"""
    auction = _lock_auction(auction_id)
    if auction.status != "active":
        db.session.commit()
        return auction  # 確定済み・取消済みはスキップ（冪等）
    if utcnow() < auction.end_time:
        db.session.commit()
        return auction

    highest = auction.highest_bid
    auction.status = "ended"
    if highest is not None:
        auction.winner_id = highest.bidder_id
        auction.winner_bid_id = highest.id
        auction.final_price = auction.current_price
        auction.artwork.status = "sold"
        # 出品者へ落札額全額を手数料なしで一度だけ加算（二重引落しなし）
        artist = auction.artwork.artist
        artist.point_balance += auction.final_price
        db.session.add(
            _tx(artist, "purchase", auction.final_price, auction.id, highest.id)
        )
        notification_service.create_notification(
            highest.bidder_id,
            "auction_won",
            "落札しました",
            f"「{auction.artwork.title}」を {auction.final_price}pt で落札しました。",
            related_auction_id=auction.id,
            related_bid_id=highest.id,
        )
        notification_service.create_notification(
            artist.id,
            "auction_won",
            "落札が確定しました",
            f"「{auction.artwork.title}」が {auction.final_price}pt で落札され、"
            "ポイントが加算されました。",
            related_auction_id=auction.id,
            related_bid_id=highest.id,
        )
    else:
        auction.winner_id = None
        auction.final_price = None
        notification_service.create_notification(
            auction.artwork.artist_id,
            "auction_lost",
            "落札不成立で終了しました",
            f"「{auction.artwork.title}」は入札がなく終了しました。",
            related_auction_id=auction.id,
        )
    db.session.commit()
    return auction


def close_expired_auctions():
    """終了対象を抽出して close_auction を実行する（定期処理から呼ぶ）。"""
    now = utcnow()
    ids = [
        row[0]
        for row in db.session.query(Auction.id).filter(
            Auction.status == "active", Auction.end_time <= now
        )
    ]
    closed = 0
    for auction_id in ids:
        auction = close_auction(auction_id)
        closed += 1
    return closed
