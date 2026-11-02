"""ポイント残高と取引履歴の操作。

残高は負にしない。変更は必ず取引履歴と同じトランザクションで行う。
"""

from __future__ import annotations

from app.extensions import db
from app.models.wallet import (
    BONUS_DRAW,
    BONUS_FIRST_LISTING,
    BONUS_SIGNUP,
    TYPE_BONUS,
    WalletTransaction,
)
from app.services.errors import InsufficientPointsError


def get_point_balance(user) -> int:
    """本人のポイント残高を取得する。"""
    return int(user.point_balance or 0)


def list_point_transactions(user, limit: int = 50) -> list[WalletTransaction]:
    """本人のポイント取引履歴を新しい順に取得する。"""
    return (
        WalletTransaction.query.filter_by(user_id=user.id)
        .order_by(WalletTransaction.created_at.desc(), WalletTransaction.id.desc())
        .limit(limit)
        .all()
    )


def adjust_balance(
    user,
    amount: int,
    transaction_type: str,
    related_auction_id: int | None = None,
    related_bid_id: int | None = None,
) -> WalletTransaction:
    """残高を変更し、履歴を記録する。

    残高が負になる場合は例外を発生させ、変更しない。
    """
    amount = int(amount)
    current = get_point_balance(user)
    if current + amount < 0:
        raise InsufficientPointsError(
            f"残高が不足しています（現在 {current}pt）。"
        )
    user.point_balance = current + amount
    transaction = WalletTransaction(
        user_id=user.id,
        transaction_type=transaction_type,
        amount=amount,
        balance_after=user.point_balance,
        related_auction_id=related_auction_id,
        related_bid_id=related_bid_id,
    )
    db.session.add(transaction)
    return transaction


def grant_bonus_points(
    user,
    bonus_type: str,
    amount: int,
    bonus_date: str = "once",
) -> bool:
    """ボーナスポイントを自動付与する。

    同一条件の付与済みなら何もしない（重複付与を防ぐ）。
    付与した場合 True を返す。
    """
    from app.models.wallet import BonusGrant

    existing = BonusGrant.query.filter_by(
        user_id=user.id, bonus_type=bonus_type, bonus_date=bonus_date
    ).first()
    if existing is not None:
        return False

    grant = BonusGrant(
        user_id=user.id,
        bonus_type=bonus_type,
        bonus_date=bonus_date,
        amount=amount,
    )
    db.session.add(grant)
    adjust_balance(user, amount, TYPE_BONUS)
    return True


def grant_signup_bonus(user, amount: int) -> bool:
    """登録ボーナス（1 アカウント 1 回）を付与する。"""
    return grant_bonus_points(user, BONUS_SIGNUP, amount)


def grant_first_listing_bonus(user, amount: int) -> bool:
    """初出品ボーナス（1 アカウント 1 回）を付与する。"""
    return grant_bonus_points(user, BONUS_FIRST_LISTING, amount)


def grant_draw_bonus(user, amount: int, bonus_date: str) -> bool:
    """描画正式保存ボーナス（日本時間 1 日 1 回）を付与する。"""
    return grant_bonus_points(user, BONUS_DRAW, amount, bonus_date=bonus_date)
