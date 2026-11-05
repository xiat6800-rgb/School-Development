"""アプリ内通知。取引の確定後に生成し、再実行でも重複させない。"""

from app.extensions import db
from app.models import Notification


def create_notification(user, notification_type, title, message,
                        related_auction_id=None, related_bid_id=None):
    notification = Notification(
        user_id=user.id,
        notification_type=notification_type,
        title=title,
        message=message,
        related_auction_id=related_auction_id,
        related_bid_id=related_bid_id,
    )
    db.session.add(notification)
    return notification


def list_user_notifications(user, limit=100):
    return (
        user.notifications.order_by(
            Notification.created_at.desc(), Notification.id.desc()
        )
        .limit(limit)
        .all()
    )


def mark_notification_read(user, notification_id):
    notification = db.session.get(Notification, notification_id)
    if notification is None or notification.user_id != user.id:
        return None
    notification.is_read = True
    return notification
