from flask import Blueprint, abort, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.services import notification_service

bp = Blueprint("notifications", __name__)


@bp.route("/notifications", methods=["GET"])
@login_required
def show_notifications():
    notifications = notification_service.list_user_notifications(current_user)
    return render_template(
        "notifications/list.html", notifications=notifications
    )


@bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_notification_read(notification_id):
    notification = notification_service.mark_notification_read(
        current_user, notification_id
    )
    if notification is None:
        abort(404)
    return redirect(url_for("notifications.show_notifications"))
