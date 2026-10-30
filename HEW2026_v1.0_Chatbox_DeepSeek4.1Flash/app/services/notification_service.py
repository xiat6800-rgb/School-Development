"""アプリ内通知の生成・取得・既読管理。"""

from ..extensions import db
from ..models import Notification


def create_notification(
    user_id,
    notification_type,
    title,
    message,
    related_auction_id=None,
    related_bid_id=None,
    dedupe_key=None,
):
    """通知を 1 件生成する。dedupe_key が既存なら生成しない。

    呼び出し元がコミットする。確定前の成功通知は生成しないこと。
    """
    if user_id is None:
        return None
    if dedupe_key:
        existing = db.session.scalar(
            db.select(Notification.id).where(Notification.dedupe_key == dedupe_key)
        )
        if existing is not None:
            return None

    notification = Notification(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        message=message,
        related_auction_id=related_auction_id,
        related_bid_id=related_bid_id,
        dedupe_key=dedupe_key,
    )
    db.session.add(notification)
    db.session.flush()
    return notification


def list_user_notifications(user_id, unread_only=False, limit=50):
    """本人の通知一覧を新しい順に取得する。"""
    statement = db.select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        statement = statement.where(Notification.is_read.is_(False))
    statement = statement.order_by(
        Notification.created_at.desc(), Notification.id.desc()
    ).limit(limit)
    return db.session.scalars(statement).all()


def count_unread(user_id):
    """未読件数を返す。"""
    return (
        db.session.scalar(
            db.select(db.func.count(Notification.id)).where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
        )
        or 0
    )


def mark_notification_read(notification_id, user_id):
    """所有者を確認して通知を既読にする。"""
    notification = db.session.get(Notification, notification_id)
    if notification is None or notification.user_id != user_id:
        return False
    notification.is_read = True
    db.session.commit()
    return True


def mark_all_read(user_id):
    """本人の未読通知をすべて既読にする。"""
    notifications = db.session.scalars(
        db.select(Notification).where(
            Notification.user_id == user_id, Notification.is_read.is_(False)
        )
    ).all()
    for notification in notifications:
        notification.is_read = True
    db.session.commit()
    return len(notifications)
