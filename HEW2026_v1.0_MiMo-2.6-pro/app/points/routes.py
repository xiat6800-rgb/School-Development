from flask import Blueprint, render_template
from flask_login import current_user, login_required

from app.services import point_service

bp = Blueprint("points", __name__)


@bp.route("/points/bonus", methods=["GET"])
@login_required
def show_bonus_points():
    grants = point_service.list_bonus_grants(current_user)
    transactions = point_service.list_point_transactions(current_user)
    return render_template(
        "points/bonus.html", grants=grants, transactions=transactions
    )


@bp.route("/points/charge", methods=["GET"])
@login_required
def show_charge():
    return render_template("points/charge.html")


@bp.route("/points/payment", methods=["GET"])
@login_required
def show_payment():
    return render_template("points/payment.html")
