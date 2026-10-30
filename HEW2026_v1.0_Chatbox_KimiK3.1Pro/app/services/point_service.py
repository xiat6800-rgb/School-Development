from flask import current_app

from app.extensions import db
from app.models import User, WalletTransaction
from app.services.common import BusinessError
from app.utils import to_jst, utcnow


def change_points(user, amount, transaction_type, dedupe_key, *, auction=None,
                  bid=None, note=""):
    """残高と履歴を同じSessionで更新し、冪等キーで二重処理を防ぐ。"""
    existing = WalletTransaction.query.filter_by(dedupe_key=dedupe_key).first()
    if existing:
        return False
    new_balance = user.point_balance + amount
    if new_balance < 0:
        raise BusinessError("ポイント残高が不足しています。")
    user.point_balance = new_balance
    db.session.add(WalletTransaction(
        user=user,
        transaction_type=transaction_type,
        amount=amount,
        balance_after=new_balance,
        auction=auction,
        bid=bid,
        dedupe_key=dedupe_key,
        note=note,
    ))
    return True


def grant_bonus_points(user, kind, *, artwork=None, auction=None):
    settings = {
        "register": (
            current_app.config["BONUS_REGISTER"], f"bonus:register:{user.id}",
            "登録ボーナス",
        ),
        "first_listing": (
            current_app.config["BONUS_FIRST_LISTING"],
            f"bonus:first-listing:{user.id}", "初出品ボーナス",
        ),
    }
    if kind == "daily_drawing":
        day = to_jst(utcnow()).date().isoformat()
        amount = current_app.config["BONUS_DAILY_DRAWING"]
        key = f"bonus:drawing:{user.id}:{day}"
        note = "正式保存ボーナス（日本時間で1日1回）"
    elif kind in settings:
        amount, key, note = settings[kind]
    else:
        raise ValueError("unknown bonus kind")
    return change_points(
        user, amount, "bonus", key, auction=auction, note=note
    )


def list_point_transactions(user):
    return WalletTransaction.query.filter_by(user_id=user.id).order_by(
        WalletTransaction.id.desc()
    ).all()
