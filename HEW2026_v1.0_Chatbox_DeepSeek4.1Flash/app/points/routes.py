"""ボーナス・チャージ・支払い・取引履歴の画面。"""

from flask import Blueprint, current_app, render_template
from flask_login import current_user, login_required

from ..constants import (
    BONUS_DAILY_SAVE,
    BONUS_FIRST_LISTING,
    BONUS_REGISTRATION,
)
from ..services import point_service

bp = Blueprint("points", __name__, url_prefix="/points")


@bp.get("/bonus")
@login_required
def show_bonus_points():
    """ボーナスの条件と獲得履歴を表示する（受け取り操作は不要）。"""
    config = current_app.config
    conditions = [
        {
            "type": BONUS_REGISTRATION,
            "label": "ユーザー登録",
            "amount": config["BONUS_REGISTRATION_POINTS"],
            "limit": "1アカウントにつき1回",
        },
        {
            "type": BONUS_FIRST_LISTING,
            "label": "初めての出品",
            "amount": config["BONUS_FIRST_LISTING_POINTS"],
            "limit": "1アカウントにつき1回",
        },
        {
            "type": BONUS_DAILY_SAVE,
            "label": "作品の正式保存",
            "amount": config["BONUS_DAILY_SAVE_POINTS"],
            "limit": "日本時間の暦日で1日1回",
        },
    ]
    granted_types = {
        grant.bonus_type
        for grant in point_service.list_user_bonuses(current_user.id, limit=100)
    }
    return render_template(
        "points/bonus.html",
        conditions=conditions,
        granted_types=granted_types,
        bonuses=point_service.list_user_bonuses(current_user.id),
        balance=current_user.point_balance,
    )


@bp.get("/charge")
@login_required
def show_charge():
    """チャージ画面。Ver0.5 では課金機能を提供しないことを明示する。"""
    return render_template(
        "points/charge.html",
        balance=current_user.point_balance,
    )


@bp.get("/payment")
@login_required
def show_payment():
    """支払い画面（遷移先のみ。Stripe 連携は行わない）。"""
    return render_template("points/payment.html")


@bp.get("/transactions")
@login_required
def transactions():
    """ポイント取引履歴を表示する。"""
    return render_template(
        "points/transactions.html",
        transactions=point_service.list_point_transactions(
            current_user.id, limit=100
        ),
        balance=current_user.point_balance,
    )
