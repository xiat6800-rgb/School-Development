"""ボーナスポイント・チャージ・支払い画面（要件定義書 5.7）。"""
from flask import Blueprint, current_app, render_template
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from app.models import WalletTransaction
from app.services import bonus_service

bp = Blueprint("points", __name__, url_prefix="/points")


@bp.route("/bonus")
@login_required
def bonus():
    history = (
        db.session.execute(
            select(WalletTransaction)
            .where(
                WalletTransaction.user_id == current_user.id,
                WalletTransaction.transaction_type == "bonus",
            )
            .order_by(WalletTransaction.created_at.desc())
            .limit(30)
        )
        .scalars()
        .all()
    )
    return render_template(
        "points/bonus.html",
        history=history,
        remaining_times=bonus_service.remaining_draw_bonus_times(current_user),
        signup_points=current_app.config["BONUS_SIGNUP_POINTS"],
        listing_points=current_app.config["BONUS_FIRST_LISTING_POINTS"],
        draw_points=current_app.config["BONUS_DRAW_POINTS"],
        draw_max_times=current_app.config["BONUS_DRAW_MAX_TIMES"],
    )


@bp.route("/charge")
@login_required
def charge():
    return render_template("points/charge.html")


@bp.route("/payment")
@login_required
def payment():
    return render_template("points/payment.html")
