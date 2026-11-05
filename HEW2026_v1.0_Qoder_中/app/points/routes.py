"""ポイント・チャージ画面のルート。Ver0.5 では課金機能を提供しない。"""
from flask import current_app, render_template
from flask_login import current_user, login_required

from ..models.point import BonusGrant
from ..services import point_service
from . import bp


@bp.route("/points/bonus")
@login_required
def show_bonus_points():
    """ボーナスの条件と獲得履歴を表示する。受け取り操作は不要。"""
    grants = (
        BonusGrant.query.filter_by(user_id=current_user.id)
        .order_by(BonusGrant.created_at.desc())
        .all()
    )
    return render_template(
        "points/bonus.html",
        grants=grants,
        signup=current_app.config["BONUS_SIGNUP_POINTS"],
        first_listing=current_app.config["BONUS_FIRST_LISTING_POINTS"],
        draw_save=current_app.config["BONUS_DRAW_SAVE_POINTS"],
        balance=point_service.get_point_balance(current_user),
    )


@bp.route("/points/charge")
@login_required
def show_charge():
    """Ver0.5 では課金未提供であることを明示するチャージ画面。"""
    return render_template(
        "points/charge.html",
        balance=point_service.get_point_balance(current_user),
    )


@bp.route("/points/payment")
@login_required
def show_payment():
    """遷移先の支払い画面（決済は実行しない）。"""
    return render_template("points/payment.html")
