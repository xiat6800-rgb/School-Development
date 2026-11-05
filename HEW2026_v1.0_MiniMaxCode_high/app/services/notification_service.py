"""アプリ内通知の生成と取得。

仕様決定事項8章の契機・対象者にだけ通知を作る。
取引の確定前に成功通知を生成せず、再実行でも重複させない。
"""

from __future__ import annotations

from app.extensions import db
from app.models.notification import Notification


def create_notification(
    user_id: int,
    notification_type: str,
    title: str,
    message: str,
    related_auction_id: int | None = None,
    related_bid_id: int | None = None,
) -> Notification:
    """通知を 1 件生成して返す。"""
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


def list_user_notifications(user, limit: int = 100) -> list[Notification]:
    """本人の通知を新しい順に取得する。"""
    return (
        Notification.query.filter_by(user_id=user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit)
        .all()
    )


def count_unread(user) -> int:
    """未読通知の件数を返す。"""
    return Notification.query.filter_by(user_id=user.id, is_read=False).count()
