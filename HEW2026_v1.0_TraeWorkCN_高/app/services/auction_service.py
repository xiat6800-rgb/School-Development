"""入札・自動入札・落札確定の業務ロジック。

要件定義書 5.4〜5.6 / 7.3:
- 対象オークション・入札者・前最高入札者をロックしてから状態・金額・残高を検証する
- 残高減算・入札履歴・ポイント取引履歴・現在価格を同一トランザクションで更新する
- 高値更新時は前最高入札者へ同額を返却する
"""
from sqlalchemy import select

from flask import current_app

from app.extensions import db
from app.models import (
    Artwork,
    Auction,
    AutoBidSetting,
    Bid,
    User,
    WalletTransaction,
)
from app.services.notification_service import notify
from app.utils import utcnow

MAX_AUTO_BID_ROUNDS = 20
MAX_BID_AMOUNT = 100_000_000


class BidError(Exception):
    """入札を受け付けられない理由を画面にそのまま表示するための例外。"""


def _lock_auction(auction_id):
    return db.session.execute(
        select(Auction).where(Auction.id == auction_id).with_for_update()
    ).scalar_one_or_none()


def _lock_users(user_ids):
    locked = {}
    for user_id in sorted(set(user_ids)):
        user = db.session.execute(
            select(User).where(User.id == user_id).with_for_update()
        ).scalar_one_or_none()
        if user is None:
            raise BidError("ユーザーが見つかりません。")
        locked[user_id] = user
    return locked


def highest_bid(auction):
    return db.session.execute(
        select(Bid)
        .where(Bid.auction_id == auction.id, Bid.bid_status == "accepted")
        .order_by(Bid.bid_amount.desc(), Bid.created_at.asc())
        .limit(1)
    ).scalar_one_or_none()


def _validate_auction(auction, bidder_id):
    if auction.status != "active":
        raise BidError("このオークションは終了しています。")
    if auction.end_time <= utcnow():
        raise BidError("終了日時を過ぎているため入札できません。")
    if auction.artwork is None:
        raise BidError("作品情報を取得できませんでした。")
    if auction.artwork.seller_id == bidder_id:
        raise BidError("出品者本人は自分のオークションに入札できません。")


def _record_bid(auction, bidder, amount, previous, locked_users, is_auto):
    if previous is not None:
        previous_bidder = locked_users.get(previous.bidder_id) or db.session.get(
            User, previous.bidder_id
        )
        if previous_bidder is not None:
            previous_bidder.point_balance = int(previous_bidder.point_balance) + int(
                previous.bid_amount
            )
            db.session.add(
                WalletTransaction(
                    user_id=previous_bidder.id,
                    transaction_type="refund",
                    amount=int(previous.bid_amount),
                    balance_after=previous_bidder.point_balance,
                    related_auction_id=auction.id,
                    related_bid_id=previous.id,
                )
            )
            if previous_bidder.id != bidder.id:
                notify(
                    previous_bidder,
                    "bid_received",
                    "高値が更新されました",
                    f"「{auction.artwork.title}」で他のユーザーが {amount}pt を入札しました。"
                    "必要であれば再度入札してください。",
                    auction_id=auction.id,
                    bid_id=previous.id,
                )

    bidder.point_balance = int(bidder.point_balance) - int(amount)
    bid = Bid(
        auction_id=auction.id,
        bidder_id=bidder.id,
        bid_amount=amount,
        is_auto_bid=is_auto,
        bid_status="accepted",
    )
    db.session.add(bid)
    db.session.flush()

    db.session.add(
        WalletTransaction(
            user_id=bidder.id,
            transaction_type="bid",
            amount=-int(amount),
            balance_after=bidder.point_balance,
            related_auction_id=auction.id,
            related_bid_id=bid.id,
        )
    )
    auction.current_price = amount

    notify(
        auction.artwork.seller,
        "bid_received",
        "入札が入りました",
        f"「{auction.artwork.title}」に {amount}pt の入札が入りました。"
        f"現在価格は {amount}pt です。",
        auction_id=auction.id,
        bid_id=bid.id,
    )
    return bid


def place_bid(auction_id, bidder_id, amount, is_auto=False):
    """手動入札を受け付け、続けて自動入札を同じトランザクションで実行する。"""
    amount = int(amount)
    if amount <= 0:
        raise BidError("入札額は 1pt 以上で入力してください。")
    if amount > MAX_BID_AMOUNT:
        raise BidError("入札額が上限を超えています。")

    auction = _lock_auction(auction_id)
    if auction is None:
        raise BidError("オークションが見つかりません。")
    _validate_auction(auction, bidder_id)
    if amount <= auction.current_price:
        raise BidError(
            f"入札額は現在価格（{auction.current_price}pt）より大きい必要があります。"
        )

    previous = highest_bid(auction)
    candidate_ids = [bidder_id] + ([previous.bidder_id] if previous else [])
    locked_users = _lock_users(candidate_ids)

    bidder = locked_users[bidder_id]
    if int(bidder.point_balance) < amount:
        raise BidError("ポイント残高が不足しています。チャージ画面をご確認ください。")

    bid = _record_bid(auction, bidder, amount, previous, locked_users, is_auto)
    _run_auto_bids(auction)
    db.session.commit()
    return bid


def _run_auto_bids(auction):
    increment = max(1, int(current_app.config["BID_INCREMENT"]))
    seller_id = auction.artwork.seller_id

    for _ in range(MAX_AUTO_BID_ROUNDS):
        current = highest_bid(auction)
        current_holder = current.bidder_id if current else None

        candidates = (
            db.session.execute(
                select(AutoBidSetting)
                .where(
                    AutoBidSetting.auction_id == auction.id,
                    AutoBidSetting.is_active.is_(True),
                    AutoBidSetting.user_id != seller_id,
                )
                .order_by(
                    AutoBidSetting.max_amount.desc(), AutoBidSetting.created_at.asc()
                )
            )
            .scalars()
            .all()
        )

        acted = False
        for setting in candidates:
            if setting.user_id == current_holder:
                continue  # 既に最高額の入札者
            next_amount = min(setting.max_amount, auction.current_price + increment)
            if next_amount <= auction.current_price:
                continue

            # 上限額が同額なら設定日時が早いユーザーを優先する（要件定義書 5.5）。
            # 上限額ちょうどまで競り上がる場面で、後から設定した同額ユーザーは譲る。
            if next_amount == setting.max_amount:
                earlier_tie = any(
                    other.user_id != setting.user_id
                    and other.max_amount == setting.max_amount
                    and (other.created_at, other.id) < (setting.created_at, setting.id)
                    for other in candidates
                )
                if earlier_tie:
                    continue

            previous = highest_bid(auction)
            ids = [setting.user_id] + ([previous.bidder_id] if previous else [])
            locked_users = _lock_users(ids)
            user = locked_users[setting.user_id]
            if int(user.point_balance) < next_amount:
                continue  # 残高不足の設定は保留し、次点の候補を試す

            _record_bid(auction, user, next_amount, previous, locked_users, True)
            acted = True
            break

        if not acted:
            break


def set_auto_bid(auction_id, user_id, max_amount):
    max_amount = int(max_amount)
    if max_amount > MAX_BID_AMOUNT:
        raise BidError("上限額が大きすぎます。")
    auction = _lock_auction(auction_id)
    if auction is None:
        raise BidError("オークションが見つかりません。")
    _validate_auction(auction, user_id)
    if max_amount <= auction.current_price:
        raise BidError(
            f"上限額は現在価格（{auction.current_price}pt）より大きく設定してください。"
        )

    setting = (
        db.session.query(AutoBidSetting)
        .filter(
            AutoBidSetting.auction_id == auction.id,
            AutoBidSetting.user_id == user_id,
        )
        .first()
    )
    if setting is None:
        setting = AutoBidSetting(
            auction_id=auction.id,
            user_id=user_id,
            max_amount=max_amount,
            is_active=True,
        )
        db.session.add(setting)
    else:
        setting.max_amount = max_amount
        setting.is_active = True
    db.session.commit()
    return setting


def stop_auto_bid(setting_id, user_id):
    setting = db.session.get(AutoBidSetting, setting_id)
    if setting is None or setting.user_id != user_id:
        return False
    setting.is_active = False
    db.session.commit()
    return True


def close_auctions(now=None):
    """終了日時を過ぎたオークションを確定する（定期実行される CLI から呼ぶ）。"""
    now = now or utcnow()
    auctions = (
        db.session.execute(
            select(Auction)
            .where(Auction.status == "active", Auction.end_time <= now)
            .with_for_update()
        )
        .scalars()
        .all()
    )

    closed = []
    for auction in auctions:
        winner_bid = highest_bid(auction)
        auction.status = "ended"
        auction.closed_reason = "time_expired"

        if winner_bid is not None:
            auction.winner_id = winner_bid.bidder_id
            auction.winner_bid_id = winner_bid.id
            auction.final_price = winner_bid.bid_amount
            if auction.artwork is not None:
                auction.artwork.status = "sold"

            winner = db.session.get(User, winner_bid.bidder_id)
            if winner is not None:
                notify(
                    winner,
                    "auction_won",
                    "落札しました",
                    f"「{auction.artwork.title}」を {winner_bid.bid_amount}pt で落札しました。",
                    auction_id=auction.id,
                    bid_id=winner_bid.id,
                )

            losing_bidder_ids = {
                bid.bidder_id
                for bid in auction.bids
                if bid.bid_status == "accepted" and bid.bidder_id != winner_bid.bidder_id
            }
            for bidder_id in losing_bidder_ids:
                loser = db.session.get(User, bidder_id)
                if loser is not None:
                    notify(
                        loser,
                        "auction_lost",
                        "落札できませんでした",
                        f"「{auction.artwork.title}」は他のユーザーが落札しました。",
                        auction_id=auction.id,
                    )

            notify(
                auction.artwork.seller,
                "auction_ending",
                "オークションが終了しました",
                f"「{auction.artwork.title}」は {winner_bid.bid_amount}pt で落札されました。",
                auction_id=auction.id,
            )
        else:
            if auction.artwork is not None:
                notify(
                    auction.artwork.seller,
                    "auction_ending",
                    "入札なしで終了しました",
                    f"「{auction.artwork.title}」は入札がないまま終了しました。",
                    auction_id=auction.id,
                )

        closed.append(auction.id)

    db.session.commit()
    return closed
