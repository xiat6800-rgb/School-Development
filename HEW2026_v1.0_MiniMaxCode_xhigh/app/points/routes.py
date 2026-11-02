"""ボーナスポイント・チャージ・支払い画面。

要件定義書 5.7章：
- ボーナスは自動付与で、受け取り操作は設けない
- チャージ／支払いは遷移先として用意するだけで、決済処理は行わない
"""

from __future__ import annotations

from flask import current_app, render_template
from flask_login import current_user, login_required

from app.models.wallet import BonusGrant
from app.points import points_bp
from app.services.point_service import get_point_balance, list_point_transactions


@points_bp.route("/points/bonus")
@login_required
def show_bonus_points():
    """ボーナスの条件と付与結果を表示する。"""
    grants = (
        BonusGrant.query.filter_by(user_id=current_user.id)
        .order_by(BonusGrant.created_at.desc(), BonusGrant.id.desc())
        .all()
    )
    return render_template(
        "points/bonus.html",
        grants=grants,
        balance=get_point_balance(current_user),
        transactions=list_point_transactions(current_user, limit=20),
        signup_points=current_app.config["BONUS_SIGNUP_POINTS"],
        first_listing_points=current_app.config["BONUS_FIRST_LISTING_POINTS"],
        draw_points=current_app.config["BONUS_DRAW_POINTS"],
    )


@points_bp.route("/points/charge")
@login_required
def show_charge():
    """チャージ画面を表示する（Ver0.5 では課金未提供）。"""
    return render_template(
        "points/charge.html", balance=get_point_balance(current_user)
    )


@points_bp.route("/points/payment")
@login_required
def show_payment():
    """支払い画面を表示する（遷移先のみ）。"""
    return render_template(
        "points/payment.html", balance=get_point_balance(current_user)
    )
