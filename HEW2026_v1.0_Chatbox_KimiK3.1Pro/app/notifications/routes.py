from flask import redirect, render_template, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Notification
from app.notifications import bp
from app.services.common import BusinessError
from app.services.notification_service import list_user_notifications


@bp.get("")
@login_required
def show_notifications():
    return render_template(
        "notifications/index.html", notifications=list_user_notifications(current_user)
    )


@bp.post("/<int:notification_id>/read")
@login_required
def mark_notification_read(notification_id):
    notification = db.session.get(Notification, notification_id)
    if not notification or notification.user_id != current_user.id:
        raise BusinessError("自分の通知だけを既読にできます。")
    notification.is_read = True
    db.session.commit()
    if notification.auction_id:
        return redirect(url_for("auctions.show_auction_detail", auction_id=notification.auction_id))
    return redirect(url_for("notifications.show_notifications"))
