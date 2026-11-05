"""ポイントサービス。残高・取引履歴・ボーナス付与を同一トランザクションで扱う。"""
from datetime import timedelta, timezone
from datetime import datetime

from flask import current_app
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models.point import BonusGrant, WalletTransaction
from ..models.user import User

JST = timezone(timedelta(hours=9))


class InsufficientPointsError(Exception):
    """ポイント残高が不足する場合に発生する。"""


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_point_balance(user):
    """本人のポイント残高を返す。"""
    return user.point_balance


def list_point_transactions(user, limit=100):
    """本人のポイント取引履歴を新しい順に返す。"""
    return (
        WalletTransaction.query.filter_by(user_id=user.id)
        .order_by(WalletTransaction.created_at.desc(), WalletTransaction.id.desc())
        .limit(limit)
        .all()
    )


def apply_points(user, transaction_type, amount,
                 related_auction_id=None, related_bid_id=None):
    """残高を増減し、取引履歴を記録する。負残高は拒否する。

    amount は増加が正・減少が負。コミットは呼び出し元が行う。
    """
    new_balance = user.point_balance + amount
    if new_balance < 0:
        raise InsufficientPointsError("ポイント残高が不足しています。")
    user.point_balance = new_balance
    tx = WalletTransaction(
        user_id=user.id,
        transaction_type=transaction_type,
        amount=amount,
        balance_after=new_balance,
        related_auction_id=related_auction_id,
        related_bid_id=related_bid_id,
    )
    db.session.add(tx)
    return tx


def grant_bonus_points(user, bonus_type, grant_key, amount=None):
    """条件・回数制限を確認してボーナスを付与する。再送では重複付与しない。

    grant_key が登録済みなら何もしない（冪等）。付与は残高・履歴と
    同一トランザクションで更新し、コミットは呼び出し元に委ねる。
    """
    if amount is None:
        amount = {
            "signup": current_app.config["BONUS_SIGNUP_POINTS"],
            "first_listing": current_app.config["BONUS_FIRST_LISTING_POINTS"],
            "draw_save": current_app.config["BONUS_DRAW_SAVE_POINTS"],
        }[bonus_type]

    if BonusGrant.query.filter_by(grant_key=grant_key).first():
        return None
    grant = BonusGrant(
        user_id=user.id, grant_key=grant_key,
        bonus_type=bonus_type, amount=amount,
    )
    db.session.add(grant)
    apply_points(user, "bonus", amount)
    try:
        db.session.flush()
    except IntegrityError:
        # 同時実行で同じ grant_key が入った場合は付与を取り消す
        db.session.rollback()
        return None
    return grant


def jst_today_key(user_id):
    """日本時間の暦日で1日1回制限するための grant_key を返す。"""
    jst_date = datetime.now(JST).date().isoformat()
    return f"draw_save:{user_id}:{jst_date}"
