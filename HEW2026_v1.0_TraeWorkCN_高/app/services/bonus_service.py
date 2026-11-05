"""ボーナスポイントの付与（要件定義書 5.7）。"""
from flask import current_app

from app.extensions import db
from app.models import User, WalletTransaction


def grant_bonus(user, points, related_auction_id=None, related_bid_id=None):
    """残高と履歴を同一トランザクションで更新する（commit は呼び出し側）。"""
    points = int(points or 0)
    if points <= 0:
        return None

    user.point_balance = int(user.point_balance or 0) + points
    transaction = WalletTransaction(
        user_id=user.id,
        transaction_type="bonus",
        amount=points,
        balance_after=user.point_balance,
        related_auction_id=related_auction_id,
        related_bid_id=related_bid_id,
    )
    db.session.add(transaction)
    db.session.flush()
    return transaction


def grant_signup_bonus(user):
    return grant_bonus(user, current_app.config["BONUS_SIGNUP_POINTS"])


def grant_draw_bonus(user):
    points = current_app.config["BONUS_DRAW_POINTS"]
    max_times = current_app.config["BONUS_DRAW_MAX_TIMES"]
    used = (
        db.session.query(WalletTransaction)
        .filter(
            WalletTransaction.user_id == user.id,
            WalletTransaction.transaction_type == "bonus",
            WalletTransaction.amount == points,
        )
        .count()
    )
    if used >= max_times:
        return None
    return grant_bonus(user, points)


def grant_listing_bonus(user, auction_id):
    """初出品のときだけ付与する（2件目以降は付与しない）。"""
    already = (
        db.session.query(WalletTransaction)
        .filter(
            WalletTransaction.user_id == user.id,
            WalletTransaction.transaction_type == "bonus",
            WalletTransaction.related_auction_id.isnot(None),
        )
        .count()
    )
    if already:
        return None
    return grant_bonus(
        user, current_app.config["BONUS_FIRST_LISTING_POINTS"], related_auction_id=auction_id
    )


def remaining_draw_bonus_times(user):
    points = current_app.config["BONUS_DRAW_POINTS"]
    max_times = current_app.config["BONUS_DRAW_MAX_TIMES"]
    used = (
        db.session.query(WalletTransaction)
        .filter(
            WalletTransaction.user_id == user.id,
            WalletTransaction.transaction_type == "bonus",
            WalletTransaction.amount == points,
        )
        .count()
    )
    return max(0, max_times - used)
