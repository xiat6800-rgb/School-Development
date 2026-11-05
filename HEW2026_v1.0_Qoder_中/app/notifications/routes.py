"""アプリ内通知のルート。メールは使用しない。"""
from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models.notification import Notification
from ..services import notification_service
from . import bp


@bp.route("/notifications")
@login_required
def show_notifications():
    """本人の通知一覧と関連商品へのリンクを表示する。"""
    notifications = notification_service.list_user_notifications(current_user)
    return render_template("notifications/list.html", notifications=notifications)


@bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_notification_read(notification_id):
    """所有者を確認して通知を既読にする。"""
    notification = db.session.get(Notification, notification_id)
    if notification is None:
        abort(404)
    if notification.user_id != current_user.id:
        abort(403)
    notification.is_read = True
    db.session.commit()
    if notification.related_auction_id:
        return redirect(
            url_for(
                "auctions.show_auction_detail",
                auction_id=notification.related_auction_id,
            )
        )
    return redirect(url_for("notifications.show_notifications"))


@bp.route("/notifications/read-all", methods=["POST"])
@login_required
def mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update(
        {"is_read": True}
    )
    db.session.commit()
    return redirect(request.referrer or url_for("notifications.show_notifications"))
