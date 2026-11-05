"""アプリ内通知の一覧と既読処理。"""

from __future__ import annotations

from flask import redirect, render_template, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models.notification import Notification
from app.notifications import notifications_bp
from app.services.errors import NotFoundError, PermissionDeniedError
from app.services.notification_service import count_unread, list_user_notifications


@notifications_bp.route("/notifications/")
@login_required
def show_notifications():
    """本人の通知一覧を表示する。"""
    notifications = list_user_notifications(current_user)
    return render_template(
        "notifications/index.html",
        notifications=notifications,
        unread_count=count_unread(current_user),
    )


@notifications_bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_notification_read(notification_id: int):
    """所有者を確認して通知を既読にする。"""
    notification = Notification.query.get(notification_id)
    if notification is None:
        raise NotFoundError("通知が見つかりません。")
    if notification.user_id != current_user.id:
        raise PermissionDeniedError("この通知を操作する権限がありません。")
    notification.is_read = True
    db.session.commit()
    return redirect(url_for("notifications.show_notifications"))
