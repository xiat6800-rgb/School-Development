"""アプリ内通知サービス。"""
from ..extensions import db
from ..models.notification import Notification


def create_notification(user_id, notification_type, title, message,
                        related_auction_id=None, related_bid_id=None):
    """取引確定後に通知を生成する。呼び出し元のトランザクションに参加する。"""
    notification = Notification(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        message=message,
        related_auction_id=related_auction_id,
        related_bid_id=related_bid_id,
    )
    db.session.add(notification)
    return notification


def list_user_notifications(user):
    """本人の通知を新しい順に取得する。"""
    return (
        Notification.query.filter_by(user_id=user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .all()
    )
