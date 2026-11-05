"""オークションの出品・入札・自動入札・終了確定。

仕様決定事項4章：
- 入札は ``auctions`` → 入札者 → 前最高入札者の順にロックする
- 入札の受理・残高減算・前最高入札者への返還・現在价格的更新は同一トランザクション
- ロック取得後のサーバー時刻で期限を確認し、自動延長はしない
- 落札確定は繰り返し実行しても二重処理しない
"""

from __future__ import annotations

from datetime import timedelta

from flask import current_app
from sqlalchemy import select

from app.extensions import db
from app.models.artwork import LISTED, SOLD
from app.models.auction import ACTIVE, ENDED, REASON_TIME_EXPIRED
from app.models.auto_bid import AutoBidSetting
from app.models.bid import ACCEPTED, Bid
from app.models.notification import (
    TYPE_AUTO_BID_STOPPED,
    TYPE_AUCTION_LOST,
    TYPE_AUCTION_UNSOLD,
    TYPE_AUCTION_WON,
    TYPE_BID_RECEIVED,
    TYPE_PRICE_UPDATED,
)
from app.models.user import User
from app.models.wallet import TYPE_BID, TYPE_REFUND, TYPE_SALE
from app.services.errors import (
    BusinessRuleError,
    InsufficientPointsError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.services.notification_service import create_notification
from app.services.point_service import adjust_balance, grant_first_listing_bonus
from app.services.tag_service import set_artwork_tags
from app.utils import utcnow

# 自動入札の連鎖回数の上限（無限実行を避ける）
MAX_AUTO_BID_STEPS = 20


# ----------------------------------------------------------------------
# 出品
# ----------------------------------------------------------------------
def create_auction(
    user,
    artwork,
    title: str,
    description: str,
    tag_ids: list[int],
    start_price: int,
    duration_minutes: int,
):
    """作品を公開してオークションを開始する。

    作者・保存済み画像・開始価格 0 以上・開催時間・タグを検証する。
    """
    from app.models.auction import Auction

    if artwork.artist_id != user.id:
        raise PermissionDeniedError("自分の作品だけを出品できます。")
    if artwork.status != "draft":
        raise BusinessRuleError("この作品は既に出品済みです。")
    if not artwork.is_saved:
        raise BusinessRuleError("画像が保存されていない作品はまだ出品できません。")
    if artwork.auction is not None:
        raise BusinessRuleError("この作品にはすでにオークションがあります。")

    try:
        price = int(start_price)
    except (TypeError, ValueError) as exc:
        raise ValidationError("開始価格を入力してください。") from exc
    if price < 0:
        raise ValidationError("開始価格は 0 以上の整数で入力してください。")

    allowed = tuple(current_app.config["AUCTION_DURATION_MINUTES"])
    try:
        minutes = int(duration_minutes)
    except (TypeError, ValueError) as exc:
        raise ValidationError("開催時間を選択してください。") from exc
    if minutes not in allowed:
        raise ValidationError("開催時間は 5分・10分・15分・20分から選択してください。")

    now = utcnow()
    end_time = now + timedelta(minutes=minutes)
    event_end = current_app.config.get("EVENT_END_AT")
    if event_end is not None and end_time > event_end:
        raise BusinessRuleError(
            "イベント終了までに開催時間を確保できないため出品できません。"
        )

    artwork.title = (title or "").strip()[:200] or artwork.title
    artwork.description = (description or "").strip()
    set_artwork_tags(artwork, tag_ids)

    auction = Auction(
        artwork=artwork,
        start_price=price,
        current_price=price,
        status=ACTIVE,
        start_time=now,
        end_time=end_time,
    )
    db.session.add(auction)
    artwork.status = LISTED
    db.session.flush()

    grant_first_listing_bonus(
        user, int(current_app.config["BONUS_FIRST_LISTING_POINTS"])
    )
    return auction


# ----------------------------------------------------------------------
# 入札
# ----------------------------------------------------------------------
def get_auction(auction_id: int):
    """オークションを 1 件取得する。"""
    from app.models.auction import Auction

    auction = Auction.query.get(auction_id)
    if auction is None:
        raise NotFoundError("オークションが見つかりません。")
    return auction


def _lock_auction(auction_id: int):
    """オークション行を ``SELECT ... FOR UPDATE`` でロックして取得する。"""
    from app.models.auction import Auction

    statement = (
        select(Auction)
        .where(Auction.id == auction_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    auction = db.session.execute(statement).scalar_one_or_none()
    if auction is None:
        raise NotFoundError("オークションが見つかりません。")
    return auction


def _lock_users(user_ids: list[int]) -> dict[int, User]:
    """指定したユーザー行を ID 昇順でロックして取得する。"""
    locked: dict[int, User] = {}
    for user_id in sorted({int(uid) for uid in user_ids if uid}):
        statement = (
            select(User)
            .where(User.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        user = db.session.execute(statement).scalar_one_or_none()
        if user is not None:
            locked[user.id] = user
    return locked


def _top_accepted_bid(auction):
    """現在の最高入札（受理済み）を返す。同額なら先着順。"""
    return (
        Bid.query.filter_by(auction_id=auction.id, bid_status=ACCEPTED)
        .order_by(Bid.bid_amount.desc(), Bid.created_at.asc(), Bid.id.asc())
        .first()
    )


def _validate_bid(auction, bidder, amount: int, now) -> None:
    """ロック取得後の最新状態に対して入札条件を検証する。"""
    if auction.status != ACTIVE:
        raise BusinessRuleError("このオークションは終了しています。")
    if now >= auction.end_time:
        raise BusinessRuleError("終了日時を過ぎているため入札できません。")
    if auction.artwork.artist_id == bidder.id:
        raise PermissionDeniedError("自分のオークションには入札できません。")
    minimum = auction.current_price + int(current_app.config["BID_MIN_INCREMENT"])
    if amount < minimum:
        raise ValidationError(
            f"入札額は現在価格（{auction.current_price}pt）を上回る必要があります。"
        )


def place_bid(
    auction_id: int,
    bidder,
    amount: int,
    is_auto: bool = False,
    expected_price: int | None = None,
) -> Bid:
    """入札を確定する。

    残高の減算・前最高入札者への返還・入札履歴・取引履歴・現在価格の
    更新を同一トランザクションで行う。
    """
    try:
        bid_amount = int(amount)
    except (TypeError, ValueError) as exc:
        raise ValidationError("入札額を入力してください。") from exc
    if bid_amount < 0:
        raise ValidationError("入札額に負の値は指定できません。")

    auction = _lock_auction(auction_id)
    now = utcnow()

    if expected_price is not None and int(expected_price) != auction.current_price:
        raise BusinessRuleError(
            "現在価格が変わりました。金額を確認して再度お試しください。"
        )

    _validate_bid(auction, bidder, bid_amount, now)

    top_bid = _top_accepted_bid(auction)
    previous_bidder_id = top_bid.bidder_id if top_bid is not None else None
    previous_amount = top_bid.bid_amount if top_bid is not None else 0

    # 最高入札者自身の増額は差額だけ、それ以外は入札全額诈取
    if previous_bidder_id == bidder.id:
        spend = bid_amount - auction.current_price
    else:
        spend = bid_amount

    lock_targets = [bidder.id]
    if previous_bidder_id and previous_bidder_id != bidder.id:
        lock_targets.append(previous_bidder_id)
    locked_users = _lock_users(lock_targets)

    bidder_row = locked_users.get(bidder.id, bidder)
    if bidder_row.point_balance < spend:
        raise InsufficientPointsError(
            f"入札には {spend}pt 必要です（残高 {bidder_row.point_balance}pt）。"
        )

    bid = Bid(
        auction=auction,
        bidder_id=bidder.id,
        bid_amount=bid_amount,
        is_auto_bid=is_auto,
        bid_status=ACCEPTED,
    )
    db.session.add(bid)
    db.session.flush()

    adjust_balance(
        bidder_row,
        -spend,
        TYPE_BID,
        related_auction_id=auction.id,
        related_bid_id=bid.id,
    )

    if previous_bidder_id and previous_bidder_id != bidder.id:
        previous_user = locked_users.get(previous_bidder_id)
        if previous_user is not None:
            adjust_balance(
                previous_user,
                previous_amount,
                TYPE_REFUND,
                related_auction_id=auction.id,
                related_bid_id=top_bid.id,
            )

    auction.current_price = bid_amount
    db.session.flush()

    _notify_bid(auction, bid, previous_bidder_id, previous_amount)
    return bid


def _notify_bid(auction, bid, previous_bidder_id, previous_amount) -> None:
    """入札に伴う通知を作る（仕様決定事項8章）。"""
    seller_id = auction.artwork.artist_id
    artwork_title = auction.artwork.title or f"作品{auction.artwork_id}"

    if seller_id != bid.bidder_id:
        create_notification(
            user_id=seller_id,
            notification_type=TYPE_BID_RECEIVED,
            title="入札を受け付けました",
            message=(
                f"「{artwork_title}」に {bid.bid_amount}pt の入札がありました。"
            ),
            related_auction_id=auction.id,
            related_bid_id=bid.id,
        )

    if previous_bidder_id and previous_bidder_id != bid.bidder_id:
        create_notification(
            user_id=previous_bidder_id,
            notification_type=TYPE_PRICE_UPDATED,
            title="価格が更新されました",
            message=(
                f"「{artwork_title}」の現在価格は {bid.bid_amount}pt になりました。"
                f"減少した {previous_amount}pt は残高に戻ります。"
            ),
            related_auction_id=auction.id,
            related_bid_id=bid.id,
        )


# ----------------------------------------------------------------------
# 自動入札
# ----------------------------------------------------------------------
def configure_auto_bid(user, auction, max_amount: int) -> AutoBidSetting:
    """自動入札の上限額を検証して設定する。"""
    try:
        limit = int(max_amount)
    except (TypeError, ValueError) as exc:
        raise ValidationError("上限額を入力してください。") from exc
    if limit < 0:
        raise ValidationError("上限額に負の値は指定できません。")
    if auction.artwork.artist_id == user.id:
        raise PermissionDeniedError("自分のオークションには自動入札できません。")
    if auction.status != ACTIVE:
        raise BusinessRuleError("このオークションは終了しています。")

    next_price = auction.current_price + int(current_app.config["BID_MIN_INCREMENT"])
    if limit < next_price:
        raise ValidationError(
            f"上限額は現在価格＋1（{next_price}pt）以上で指定してください。"
        )

    top_bid = _top_accepted_bid(auction)
    is_top = top_bid is not None and top_bid.bidder_id == user.id
    required = 1 if is_top else next_price
    if user.point_balance < required:
        raise InsufficientPointsError(
            f"次の入札額 {required}pt を支払える残高が必要です"
            f"（残高 {user.point_balance}pt）。"
        )

    setting = AutoBidSetting.query.filter_by(
        auction_id=auction.id, user_id=user.id
    ).first()
    if setting is None:
        setting = AutoBidSetting(
            auction_id=auction.id, user_id=user.id, max_amount=limit
        )
        db.session.add(setting)
    else:
        if limit < (top_bid.bid_amount if is_top and top_bid else 0):
            raise ValidationError(
                "上限を現在の受理済み入札額より低く変更することはできません。"
            )
        setting.max_amount = limit
        setting.is_active = True
    db.session.flush()
    return setting


def stop_auto_bid(user, auction) -> AutoBidSetting:
    """本人の自動入札を停止する。受理済み入札は取り消さない。"""
    setting = AutoBidSetting.query.filter_by(
        auction_id=auction.id, user_id=user.id
    ).first()
    if setting is None:
        raise NotFoundError("自動入札の設定がありません。")
    setting.is_active = False
    db.session.flush()
    return setting


def _select_auto_bid_candidate(auction) -> list[AutoBidSetting]:
    """次の入札候補を並べる。

    上限額が高い順、上限が同じなら設定が古い順（同額の上限は
    先に設定したユーザーを優先）。
    """
    return (
        AutoBidSetting.query.filter_by(auction_id=auction.id, is_active=True)
        .filter(AutoBidSetting.max_amount > auction.current_price)
        .order_by(
            AutoBidSetting.max_amount.desc(),
            AutoBidSetting.created_at.asc(),
            AutoBidSetting.id.asc(),
        )
        .all()
    )


def process_auto_bids(auction) -> list[Bid]:
    """他者の入札に応じて自動入札を競り上げる。

    勝つために必要な額だけ 1pt 単位で競り上げ、上限全額は確保しない。
    残高不足なら自動入札を停止し本人へ通知する。
    """
    placed: list[Bid] = []
    for _ in range(MAX_AUTO_BID_STEPS):
        candidates = _select_auto_bid_candidate(auction)
        if not candidates:
            break
        candidate = candidates[0]
        runner = candidates[1] if len(candidates) > 1 else None
        top_bid = _top_accepted_bid(auction)
        if top_bid is not None and top_bid.bidder_id == candidate.user_id:
            # すでに先頭。競り上げはこれ以上必要ない
            break

        target = auction.current_price + int(current_app.config["BID_MIN_INCREMENT"])
        if runner is not None and runner.max_amount >= target:
            # 2 番目に高い上限額に勝つにはその上限＋1 必要
            target = min(candidate.max_amount, runner.max_amount + 1)
        else:
            target = min(candidate.max_amount, target)
        if target <= auction.current_price:
            break

        candidate_user = db.session.get(User, candidate.user_id)
        if candidate_user is None:
            candidate.is_active = False
            continue
        spend = (
            target - auction.current_price
            if top_bid is not None and top_bid.bidder_id == candidate_user.id
            else target
        )
        if candidate_user.point_balance < spend:
            candidate.is_active = False
            create_notification(
                user_id=candidate_user.id,
                notification_type=TYPE_AUTO_BID_STOPPED,
                title="自動入札を停止しました",
                message=(
                    "残高不足のため自動入札を停止しました。残高を確認してください。"
                ),
                related_auction_id=auction.id,
            )
            break

        placed.append(
            place_bid(
                auction.id,
                candidate_user,
                target,
                is_auto=True,
            )
        )
    return placed


# ----------------------------------------------------------------------
# 終了・落札
# ----------------------------------------------------------------------
def close_auction(auction_id: int):
    """期限到達済みの 1 件を確定する。

    繰り返し実行しても二重処理しない。落札者がいる場合は出品者へ
    落札額全額を手数料なしで加算する。
    """
    auction = _lock_auction(auction_id)
    if auction.status != ACTIVE:
        return auction

    top_bid = _top_accepted_bid(auction)
    auction.status = ENDED
    auction.closed_reason = REASON_TIME_EXPIRED

    if top_bid is None:
        auction.winner_id = None
        auction.winner_bid_id = None
        auction.final_price = None
        create_notification(
            user_id=auction.artwork.artist_id,
            notification_type=TYPE_AUCTION_UNSOLD,
            title="オークションは落札者なしで終了しました",
            message=(
                f"「{auction.artwork.title or '作品'}」は入札がなく落札不成立となりました。"
            ),
            related_auction_id=auction.id,
        )
        db.session.flush()
        return auction

    auction.winner_id = top_bid.bidder_id
    auction.winner_bid_id = top_bid.id
    auction.final_price = top_bid.bid_amount
    auction.artwork.status = SOLD

    locked_users = _lock_users([auction.artwork.artist_id])
    seller = locked_users.get(auction.artwork.artist_id)
    if seller is not None:
        adjust_balance(
            seller,
            top_bid.bid_amount,
            TYPE_SALE,
            related_auction_id=auction.id,
            related_bid_id=top_bid.id,
        )

    create_notification(
        user_id=top_bid.bidder_id,
        notification_type=TYPE_AUCTION_WON,
        title="落札しました",
        message=(
            f"「{auction.artwork.title or '作品'}」を {top_bid.bid_amount}pt で"
            "落札しました。"
        ),
        related_auction_id=auction.id,
        related_bid_id=top_bid.id,
    )
    create_notification(
        user_id=auction.artwork.artist_id,
        notification_type=TYPE_AUCTION_LOST,
        title="作品，落札されました",
        message=(
            f"「{auction.artwork.title or '作品'}」は {top_bid.bid_amount}pt で"
            "落札されました。落札額全額が残高に加算されます。"
        ),
        related_auction_id=auction.id,
        related_bid_id=top_bid.id,
    )
    db.session.flush()
    return auction


def close_expired_auctions() -> list:
    """終了対象を抽出して確定する。"""
    from app.models.auction import Auction

    now = utcnow()
    expired = (
        Auction.query.filter(Auction.status == ACTIVE)
        .filter(Auction.end_time <= now)
        .order_by(Auction.end_time.asc())
        .all()
    )
    closed = []
    for auction in expired:
        closed.append(close_auction(auction.id))
    return closed
