"""ポイント残高・取引履歴・ボーナス付与。"""

from datetime import datetime, timedelta, timezone

from flask import current_app

from app.extensions import db
from app.models import BonusGrant, User, WalletTransaction


class InsufficientPointsError(Exception):
    """残高不足で入札・自動入札できない。"""


def get_point_balance(user):
    return user.point_balance


def list_point_transactions(user, limit=50):
    return (
        user.wallet_transactions.order_by(
            WalletTransaction.created_at.desc(), WalletTransaction.id.desc()
        )
        .limit(limit)
        .all()
    )


def _record_transaction(user, transaction_type, amount, related_auction_id=None,
                        related_bid_id=None):
    """残高と取引履歴を同一トランザクションで更新する。"""
    new_balance = user.point_balance + amount
    if new_balance < 0:
        raise InsufficientPointsError("ポイント残高が不足しています。")
    user.point_balance = new_balance
    txn = WalletTransaction(
        user_id=user.id,
        transaction_type=transaction_type,
        amount=amount,
        balance_after=new_balance,
        related_auction_id=related_auction_id,
        related_bid_id=related_bid_id,
    )
    db.session.add(txn)
    return txn


def deduct_for_bid(user, amount, bid=None, auction=None):
    """入札消費。amount は減少額（正の値）。"""
    if amount < 0:
        raise ValueError("amount must be >= 0")
    return _record_transaction(
        user,
        WalletTransaction.TYPE_BID,
        -amount,
        related_auction_id=auction.id if auction else None,
        related_bid_id=bid.id if bid else None,
    )


def refund_bid_points(user, amount, bid=None, auction=None):
    """高値更新による未返還額の返還。呼び出し元のトランザクションに参加する。"""
    return _record_transaction(
        user,
        WalletTransaction.TYPE_REFUND,
        amount,
        related_auction_id=auction.id if auction else None,
        related_bid_id=bid.id if bid else None,
    )


def credit_sale(user, amount, auction):
    """落札確定時の出品者への全額加算（手数料なし）。"""
    return _record_transaction(
        user,
        WalletTransaction.TYPE_SALE,
        amount,
        related_auction_id=auction.id,
    )


def drawing_save_period_key():
    """日本時間の暦日キー（YYYY-MM-DD）。

    JST は UTC+9 固定（夏時間なし）のため、tz データベースに
    依存しない固定オフセットで計算する。
    """
    jst = timezone(timedelta(hours=9))
    now_jst = datetime.now(timezone.utc).astimezone(jst)
    return now_jst.strftime("%Y-%m-%d")


def grant_bonus_points(user, bonus_type, amount, period_key=""):
    """条件達成ボーナスを自動付与する。再送・再実行では重複付与しない。

    付与できた場合に True、既に付与済みでスキップした場合に False を返す。
    """
    exists = BonusGrant.query.filter_by(
        user_id=user.id, bonus_type=bonus_type, period_key=period_key
    ).first()
    if exists:
        return False
    grant = BonusGrant(
        user_id=user.id, bonus_type=bonus_type, period_key=period_key, amount=amount
    )
    db.session.add(grant)
    db.session.flush()
    _record_transaction(
        user, WalletTransaction.TYPE_BONUS, amount
    )
    return True


def grant_register_bonus(user):
    return grant_bonus_points(
        user, BonusGrant.TYPE_REGISTER,
        current_app.config["BONUS_REGISTER"],
    )


def grant_first_listing_bonus(user):
    return grant_bonus_points(
        user, BonusGrant.TYPE_FIRST_LISTING,
        current_app.config["BONUS_FIRST_LISTING"],
    )


def grant_drawing_save_bonus(user):
    return grant_bonus_points(
        user, BonusGrant.TYPE_DRAWING_SAVE,
        current_app.config["BONUS_DRAWING_SAVE"],
        period_key=drawing_save_period_key(),
    )


def list_bonus_grants(user):
    return (
        user.bonus_grants.order_by(BonusGrant.created_at.desc(), BonusGrant.id.desc())
        .all()
    )
