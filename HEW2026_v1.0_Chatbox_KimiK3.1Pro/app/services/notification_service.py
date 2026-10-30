from app.extensions import db
from app.models import Notification


def create_notification(user, notification_type, title, message, dedupe_key,
                        *, auction=None):
    if Notification.query.filter_by(dedupe_key=dedupe_key).first():
        return None
    notification = Notification(
        user=user,
        notification_type=notification_type,
        title=title,
        message=message,
        auction=auction,
        dedupe_key=dedupe_key,
    )
    db.session.add(notification)
    return notification


def list_user_notifications(user):
    return Notification.query.filter_by(user_id=user.id).order_by(
        Notification.id.desc()
    ).all()
