"""出品・入札・自動入札・落札確定。

入札はロック取得後のサーバー時刻・最新状態で検証し、
残高更新・入札履歴・ポイント取引履歴・現在価格を同一トランザクションで処理する。
"""

from datetime import timedelta

from flask import current_app

from app.extensions import db
from app.models import Auction, Artwork, AutoBidSetting, Bid, Notification, User
from app.services import notification_service, point_service
from app.services.event_service import get_server_now, validate_event_operation

LISTING_DURATIONS = (5, 10, 15, 20)
DEFAULT_LISTING_DURATION = 10
MIN_EVENT_REMAINING_SECONDS = 5 * 60
MAX_AUTO_BID_STEPS = 50


class AuctionError(Exception):
    """出品・入札条件を満たさない。"""


class AuctionNotOpenError(AuctionError):
    """開催中でない、または終了日時を過ぎている。"""


class BidRejectedError(AuctionError):
    """入札条件（本人・金額・残高・価格変動）を満たさない。"""


class AutoBidConfigError(AuctionError):
    """自動入札の設定条件を満たさない。"""


def _lock_auction(auction_id):
    return Auction.query.filter_by(id=auction_id).with_for_update().first()


def get_current_top_bid(auction):
    return (
        Bid.query.filter_by(auction_id=auction.id, bid_status=Bid.STATUS_ACCEPTED)
        .order_by(Bid.bid_amount.desc(), Bid.id.desc())
        .first()
    )


def create_auction(artwork, user, title, description, tag_ids,
                   start_price, duration_minutes=DEFAULT_LISTING_DURATION):
    """下書きを公開して競売を開始する。出品確定と同時に開始する。"""
    from app.services import tag_service

    validate_event_operation("list")
    if artwork.artist_id != user.id:
        raise AuctionError("自分の作品だけ出品できます。")
    if artwork.status != Artwork.STATUS_DRAFT:
        raise AuctionError("この作品は出品できません。")
    if not artwork.is_formally_saved or not artwork.image_path:
        raise AuctionError("正式保存済みの画像が必要です。")
    if not isinstance(start_price, int) or isinstance(start_price, bool):
        raise AuctionError("開始価格は整数で入力してください。")
    if start_price < 0:
        raise AuctionError("開始価格は0以上の整数ptにしてください。")
    if duration_minutes not in LISTING_DURATIONS:
        raise AuctionError("開催時間は5・10・15・20分から選んでください。")

    end_at = current_app.config.get("EVENT_END_AT")
    now = get_server_now()
    if end_at is not None:
        remaining = (end_at - now).total_seconds()
        if remaining < MIN_EVENT_REMAINING_SECONDS:
            raise AuctionError("イベント終了が近いため出品できません。")
        if now + timedelta(minutes=duration_minutes) > end_at:
            raise AuctionError(
                "イベント終了までに開催時間を確保できないため出品できません。"
            )

    open_auction = Auction.query.filter_by(
        artwork_id=artwork.id, status=Auction.STATUS_ACTIVE
    ).first()
    if open_auction is not None:
        raise AuctionError("この作品はすでに出品中です。")

    title = (title or "").strip()
    if not title:
        raise AuctionError("タイトルを入力してください。")
    if len(title) > 200:
        raise AuctionError("タイトルは200文字以内にしてください。")

    artwork.title = title
    artwork.description = (description or "").strip() or None
    artwork.status = Artwork.STATUS_LISTED

    auction = Auction(
        artwork_id=artwork.id,
        start_price=start_price,
        current_price=start_price,
        status=Auction.STATUS_ACTIVE,
        start_time=now,
        end_time=now + timedelta(minutes=duration_minutes),
    )
    db.session.add(auction)
    db.session.flush()

    if tag_ids:
        tag_service.set_artwork_tags(artwork, tag_ids)

    point_service.grant_first_listing_bonus(user)
    db.session.commit()
    return auction


def _validate_bid_locked(auction, bidder, amount, confirmed_price=None):
    if auction.status != Auction.STATUS_ACTIVE:
        raise AuctionNotOpenError("このオークションは終了しています。")
    now = get_server_now()
    if now >= auction.end_time:
        raise AuctionNotOpenError("終了日時を過ぎたため入札できません。")
    artwork = auction.artwork
    if artwork.artist_id == bidder.id:
        raise BidRejectedError("自分の作品には入札できません。")
    if confirmed_price is not None and confirmed_price != auction.current_price:
        raise BidRejectedError(
            "価格が変動しました。最新価格を確認して再度お試しください。"
        )
    if not isinstance(amount, int) or isinstance(amount, bool):
        raise BidRejectedError("入札額は整数のptで入力してください。")
    if amount < auction.current_price + 1:
        raise BidRejectedError("入札額は現在価格＋1pt以上にしてください。")

    top_bid = get_current_top_bid(auction)
    if top_bid is not None and top_bid.bidder_id == bidder.id:
        cost = amount - auction.current_price
    else:
        cost = amount
    if bidder.point_balance < cost:
        raise BidRejectedError("ポイント残高が不足しています。")


def _place_bid_locked(auction, bidder, amount, is_auto_bid=False,
                      confirmed_price=None):
    """検証済み入札を確定する。呼び出し元がトランザクションを管理する。"""
    _validate_bid_locked(auction, bidder, amount, confirmed_price)

    top_bid = get_current_top_bid(auction)
    bid = Bid(
        auction_id=auction.id,
        bidder_id=bidder.id,
        bid_amount=amount,
        is_auto_bid=is_auto_bid,
        bid_status=Bid.STATUS_ACCEPTED,
    )
    db.session.add(bid)
    db.session.flush()

    artwork = auction.artwork
    if top_bid is not None and top_bid.bidder_id == bidder.id:
        point_service.deduct_for_bid(
            bidder, amount - auction.current_price, bid, auction
        )
    else:
        if top_bid is not None:
            point_service.refund_bid_points(
                top_bid.bidder, top_bid.bid_amount, top_bid, auction
            )
            notification_service.create_notification(
                top_bid.bidder,
                Notification.TYPE_OUTBID,
                "高値更新のお知らせ",
                f"「{artwork.title}」であなたの入札を上回りました。"
                f"（現在価格 {amount}pt）",
                related_auction_id=auction.id,
                related_bid_id=top_bid.id,
            )
        point_service.deduct_for_bid(bidder, amount, bid, auction)

    auction.current_price = amount

    notification_service.create_notification(
        artwork.artist,
        Notification.TYPE_BID_RECEIVED,
        "入札受付のお知らせ",
        f"「{artwork.title}」に {amount}pt の入札が入りました。",
        related_auction_id=auction.id,
        related_bid_id=bid.id,
    )
    return bid


def place_bid(auction_id, bidder, amount, confirmed_price=None):
    """手動入札。同一トランザクションで整合を保つ。"""
    auction = _lock_auction(auction_id)
    if auction is None:
        raise AuctionError("オークションが見つかりません。")
    bidder = db.session.get(User, bidder.id)
    bid = _place_bid_locked(
        auction, bidder, amount, is_auto_bid=False, confirmed_price=confirmed_price
    )
    process_auto_bids(auction)
    db.session.commit()
    return bid


def _active_settings(auction):
    return (
        AutoBidSetting.query.filter_by(auction_id=auction.id, is_active=True)
        .order_by(AutoBidSetting.max_amount.desc(), AutoBidSetting.created_at.asc())
        .all()
    )


def _competition_entries(auction, top_bid):
    """(強さ, 優先時刻, user_id, setting) の一覧。

    現在の最高入札者は「その入札額または自分の自動入札上限」で参加し、
    自動入札設定は上限が現在価格を超えるものだけが競り上げに参加する。
    強さが同額なら先に設定したものを優先する。
    """
    entries = []
    settings = _active_settings(auction)
    setting_by_user = {s.user_id: s for s in settings}
    if top_bid is not None:
        top_setting = setting_by_user.get(top_bid.bidder_id)
        strength = top_bid.bid_amount
        if top_setting is not None:
            strength = max(strength, top_setting.max_amount)
        entries.append((strength, top_bid.created_at, top_bid.bidder_id, top_setting))
    for setting in settings:
        if top_bid is not None and setting.user_id == top_bid.bidder_id:
            continue
        if setting.max_amount <= auction.current_price:
            continue
        entries.append(
            (setting.max_amount, setting.created_at, setting.user_id, setting)
        )
    return entries


def process_auto_bids(auction):
    """必要な額だけ自動で競り上げる（上限代理入札）。

    全員の上限から実質の勝者と最小の勝ち額を決めて入札する。
    上限が同額なら先に設定したユーザーが勝つ。上限全額は確保せず、
    実際の入札額だけを消費する。残高不足は停止・本人通知。
    """
    for _ in range(MAX_AUTO_BID_STEPS):
        if auction.status != Auction.STATUS_ACTIVE:
            break
        if get_server_now() >= auction.end_time:
            break
        top_bid = get_current_top_bid(auction)
        entries = _competition_entries(auction, top_bid)
        if not entries:
            break
        entries.sort(key=lambda e: (-e[0], e[1]))
        strength, _, user_id, setting = entries[0]
        is_top = top_bid is not None and top_bid.bidder_id == user_id
        # 競争相手がいなければ引き上げない
        if is_top and len(entries) == 1:
            break
        second_strength = entries[1][0] if len(entries) > 1 else auction.current_price
        winning_price = min(
            strength,
            max(auction.current_price + 1, second_strength + 1),
        )
        if winning_price <= auction.current_price:
            break

        if is_top:
            if top_bid.bid_amount >= winning_price:
                break
            cost = winning_price - auction.current_price
        else:
            cost = winning_price

        user = db.session.get(User, user_id)
        if user.point_balance < cost:
            if setting is not None:
                setting.is_active = False
                notification_service.create_notification(
                    user,
                    Notification.TYPE_AUTO_BID_STOPPED,
                    "自動入札を停止しました",
                    f"「{auction.artwork.title}」の自動入札は"
                    "ポイント残高不足のため停止しました。",
                    related_auction_id=auction.id,
                )
            continue
        _place_bid_locked(auction, user, winning_price, is_auto_bid=True)


def configure_auto_bid(user, auction_id, max_amount):
    """自動入札の上限額を設定する。設定直後から判定する。"""
    auction = _lock_auction(auction_id)
    if auction is None:
        raise AutoBidConfigError("オークションが見つかりません。")
    if auction.status != Auction.STATUS_ACTIVE or get_server_now() >= auction.end_time:
        raise AutoBidConfigError("このオークションは終了しています。")
    if auction.artwork.artist_id == user.id:
        raise AutoBidConfigError("自分の作品には自動入札を設定できません。")
    if not isinstance(max_amount, int) or isinstance(max_amount, bool):
        raise AutoBidConfigError("上限額は整数のptで入力してください。")
    if max_amount < 0:
        raise AutoBidConfigError("上限額は0以上の整数ptにしてください。")

    user = db.session.get(User, user.id)
    setting = AutoBidSetting.query.filter_by(
        auction_id=auction.id, user_id=user.id
    ).with_for_update().first()

    top_bid = get_current_top_bid(auction)
    is_top = top_bid is not None and top_bid.bidder_id == user.id
    if setting is not None and setting.is_active and is_top:
        if max_amount < auction.current_price:
            raise AutoBidConfigError(
                "上限を現在の受理済み入札額より低くは変更できません。"
            )

    required = 1 if is_top else auction.current_price + 1
    if user.point_balance < required:
        raise AutoBidConfigError(
            "次の入札に必要なポイント残高が足りません。"
        )

    if setting is None:
        setting = AutoBidSetting(
            auction_id=auction.id, user_id=user.id, max_amount=max_amount,
            is_active=True,
        )
        db.session.add(setting)
    else:
        setting.max_amount = max_amount
        setting.is_active = True
    db.session.flush()

    process_auto_bids(auction)
    db.session.commit()
    return setting


def stop_auto_bid(user, auction_id):
    """本人の自動入札を停止する。受理済み入札は維持する。"""
    setting = AutoBidSetting.query.filter_by(
        auction_id=auction_id, user_id=user.id
    ).first()
    if setting is None:
        raise AutoBidConfigError("自動入札の設定が見つかりません。")
    setting.is_active = False
    db.session.commit()
    return setting


def close_auction(auction):
    """期限到達済みの1件を確定する。再実行しても二重処理しない。"""
    if auction.status != Auction.STATUS_ACTIVE:
        return auction
    top_bid = get_current_top_bid(auction)
    artwork = auction.artwork
    if top_bid is not None:
        auction.winner_id = top_bid.bidder_id
        auction.winner_bid_id = top_bid.id
        auction.final_price = top_bid.bid_amount
        artwork.status = Artwork.STATUS_SOLD
        point_service.credit_sale(artwork.artist, top_bid.bid_amount, auction)
        notification_service.create_notification(
            top_bid.bidder,
            Notification.TYPE_AUCTION_WON,
            "落札しました",
            f"「{artwork.title}」を {top_bid.bid_amount}pt で落札しました。",
            related_auction_id=auction.id,
            related_bid_id=top_bid.id,
        )
        notification_service.create_notification(
            artwork.artist,
            Notification.TYPE_AUCTION_SOLD,
            "落札が確定しました",
            f"「{artwork.title}」が {top_bid.bid_amount}pt で落札されました。",
            related_auction_id=auction.id,
            related_bid_id=top_bid.id,
        )
    else:
        notification_service.create_notification(
            artwork.artist,
            Notification.TYPE_AUCTION_UNSOLD,
            "オークションが終了しました",
            f"「{artwork.title}」は入札がなく未落札で終了しました。",
            related_auction_id=auction.id,
        )

    auction.status = Auction.STATUS_ENDED
    auction.closed_reason = "time_expired"
    AutoBidSetting.query.filter_by(auction_id=auction.id).update(
        {"is_active": False}
    )
    return auction


def close_expired_auctions(now=None):
    """終了対象を抽出して close_auction を実行する。"""
    now = now or get_server_now()
    expired = (
        Auction.query.filter(
            Auction.status == Auction.STATUS_ACTIVE,
            Auction.end_time <= now,
        )
        .order_by(Auction.end_time.asc())
        .all()
    )
    closed = []
    for auction in expired:
        close_auction(auction)
        closed.append(auction)
    if closed:
        db.session.commit()
    return closed


def can_download_artwork(user, artwork):
    """作者と落札確定済みの落札者だけが原寸PNG・ZIPを取得できる。"""
    if user is None or not user.is_authenticated:
        return False
    if artwork.artist_id == user.id:
        return True
    for auction in artwork.auctions:
        if (
            auction.status == Auction.STATUS_ENDED
            and auction.winner_id == user.id
            and auction.winner_bid_id is not None
        ):
            return True
    return False
