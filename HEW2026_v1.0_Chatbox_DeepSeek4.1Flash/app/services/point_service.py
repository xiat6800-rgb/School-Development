"""ポイント残高・取引履歴・ボーナス付与を扱う。"""

from flask import current_app

from ..clock import jst_date, utcnow
from ..constants import (
    BONUS_DAILY_SAVE,
    BONUS_FIRST_LISTING,
    BONUS_REGISTRATION,
    BONUS_TYPE_LABELS,
    WALLET_TYPE_BONUS,
)
from ..extensions import db
from ..models import BonusGrant, User, WalletTransaction
from .errors import InsufficientPointsError, ValidationError


def get_point_balance(user_id):
    """本人のポイント残高を取得する。"""
    user = db.session.get(User, user_id)
    return user.point_balance if user else 0


def add_points(
    user,
    amount,
    transaction_type,
    related_auction_id=None,
    related_bid_id=None,
    memo=None,
):
    """残高を増減し、同一トランザクションで履歴を記録する。

    残高は負にしない。呼び出し元がコミットする。
    """
    amount = int(amount)
    if amount == 0:
        return None
    new_balance = user.point_balance + amount
    if new_balance < 0:
        raise InsufficientPointsError("ポイント残高が不足しています。")
    user.point_balance = new_balance
    transaction = WalletTransaction(
        user_id=user.id,
        transaction_type=transaction_type,
        amount=amount,
        balance_after=new_balance,
        related_auction_id=related_auction_id,
        related_bid_id=related_bid_id,
        memo=memo,
    )
    db.session.add(transaction)
    db.session.flush()
    return transaction


def list_point_transactions(user_id, limit=50):
    """本人のポイント取引履歴を新しい順に取得する。"""
    return db.session.scalars(
        db.select(WalletTransaction)
        .where(WalletTransaction.user_id == user_id)
        .order_by(WalletTransaction.created_at.desc(), WalletTransaction.id.desc())
        .limit(limit)
    ).all()


def _bonus_amount(bonus_type):
    config = current_app.config
    if bonus_type == BONUS_REGISTRATION:
        return config["BONUS_REGISTRATION_POINTS"]
    if bonus_type == BONUS_FIRST_LISTING:
        return config["BONUS_FIRST_LISTING_POINTS"]
    if bonus_type == BONUS_DAILY_SAVE:
        return config["BONUS_DAILY_SAVE_POINTS"]
    raise ValidationError(f"未知のボーナス種別です: {bonus_type}")


def _grant_key(bonus_type, user_id, now):
    if bonus_type == BONUS_DAILY_SAVE:
        # 日本時間の暦日で 1 日 1 回
        return f"{bonus_type}:{user_id}:{jst_date(now).isoformat()}"
    # 1 アカウント 1 回
    return f"{bonus_type}:{user_id}"


def grant_bonus_points(user, bonus_type, now=None):
    """条件達成時にボーナスを自動付与する。

    受け取り操作は不要。同じ条件の再送では付与しない。
    戻り値は BonusGrant。付与済みなら None。
    """
    now = now or utcnow()
    amount = _bonus_amount(bonus_type)
    if amount <= 0:
        return None

    key = _grant_key(bonus_type, user.id, now)
    existing = db.session.scalar(
        db.select(BonusGrant).where(BonusGrant.grant_key == key)
    )
    if existing is not None:
        return None

    transaction = add_points(
        user,
        amount,
        WALLET_TYPE_BONUS,
        memo=BONUS_TYPE_LABELS.get(bonus_type, bonus_type),
    )
    grant = BonusGrant(
        user_id=user.id,
        bonus_type=bonus_type,
        grant_key=key,
        amount=amount,
        transaction_id=transaction.id if transaction else None,
        created_at=now,
    )
    db.session.add(grant)
    db.session.flush()
    return grant


def list_user_bonuses(user_id, limit=30):
    """ボーナスの獲得履歴を新しい順に取得する。"""
    return db.session.scalars(
        db.select(BonusGrant)
        .where(BonusGrant.user_id == user_id)
        .order_by(BonusGrant.created_at.desc(), BonusGrant.id.desc())
        .limit(limit)
    ).all()
