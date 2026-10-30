from flask import render_template
from flask_login import current_user, login_required

from app.points import bp
from app.services.point_service import list_point_transactions


@bp.get("/bonus")
@login_required
def show_bonus_points():
    transactions = [t for t in list_point_transactions(current_user) if t.transaction_type == "bonus"]
    return render_template("points/bonus.html", transactions=transactions)


@bp.get("/charge")
@login_required
def show_charge():
    return render_template("points/charge.html")


@bp.get("/payment")
@login_required
def show_payment():
    return render_template("points/payment.html")
