"""アプリ内通知（要件定義書 5.9）。"""
from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from app.models import Notification
from app.utils import safe_next

bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@bp.route("/")
@login_required
def index():
    notifications = (
        db.session.execute(
            select(Notification)
            .where(Notification.user_id == current_user.id)
            .order_by(Notification.created_at.desc())
            .limit(100)
        )
        .scalars()
        .all()
    )
    return render_template("notifications/index.html", notifications=notifications)


@bp.route("/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_read(notification_id):
    notification = db.session.get(Notification, notification_id)
    if notification is None:
        abort(404)
    if notification.user_id != current_user.id:
        abort(403)
    notification.is_read = True
    db.session.commit()
    return redirect(safe_next(url_for("notifications.index")))


@bp.route("/read-all", methods=["POST"])
@login_required
def mark_all_read():
    (
        db.session.query(Notification)
        .filter(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
        .update({Notification.is_read: True}, synchronize_session=False)
    )
    db.session.commit()
    flash("すべての通知を既読にしました。", "info")
    return redirect(url_for("notifications.index"))
