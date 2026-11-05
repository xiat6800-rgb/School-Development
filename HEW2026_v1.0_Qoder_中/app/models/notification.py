"""アプリ内通知モデル。メール配信は行わない（仕様決定事項 8章）。"""
from datetime import datetime, timezone

from ..extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'), primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id"), nullable=False, index=True
    )
    # bid_received / outbid / auction_won / auction_lost / auto_bid_stopped
    notification_type = db.Column(db.String(30), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    related_auction_id = db.Column(db.BigInteger, nullable=True)
    related_bid_id = db.Column(db.BigInteger, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User", backref="notifications")

    __table_args__ = (
        db.Index("idx_notifications_user_read_created", "user_id", "is_read", "created_at"),
    )
