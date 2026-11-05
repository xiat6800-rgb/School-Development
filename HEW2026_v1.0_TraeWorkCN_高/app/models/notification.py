"""notifications / notification_deliveries。"""
from app.extensions import db
from app.models.types import ID_TYPE
from app.utils import utcnow


class Notification(db.Model):
    __tablename__ = "notifications"
    __table_args__ = (
        db.Index("idx_notifications_user_read", "user_id", "is_read", "created_at"),
        db.Index("idx_notifications_auction", "related_auction_id"),
    )

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    user_id = db.Column(ID_TYPE, db.ForeignKey("users.id"), nullable=False)
    notification_type = db.Column(
        db.Enum(
            "bid_received",
            "auction_ending",
            "auction_won",
            "auction_lost",
            "payment_result",
            name="notification_type",
        ),
        nullable=False,
    )
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    related_auction_id = db.Column(
        ID_TYPE, db.ForeignKey("auctions.id"), nullable=True
    )
    related_bid_id = db.Column(ID_TYPE, db.ForeignKey("bids.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User", backref=db.backref("notifications", lazy="dynamic"))
    auction = db.relationship(
        "Auction", backref=db.backref("notifications", lazy="dynamic")
    )
    bid = db.relationship("Bid", backref=db.backref("notifications", lazy="dynamic"))
    deliveries = db.relationship(
        "NotificationDelivery",
        back_populates="notification",
        cascade="all, delete-orphan",
    )


class NotificationDelivery(db.Model):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        db.Index("idx_deliveries_status", "delivery_status", "created_at"),
        db.Index("idx_deliveries_notification", "notification_id"),
    )

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    notification_id = db.Column(
        ID_TYPE, db.ForeignKey("notifications.id"), nullable=False
    )
    channel = db.Column(
        db.Enum("email", name="delivery_channel"), nullable=False, default="email"
    )
    recipient = db.Column(db.String(255), nullable=False)
    delivery_status = db.Column(
        db.Enum("pending", "sent", "failed", name="delivery_status"),
        nullable=False,
        default="pending",
    )
    sent_at = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    notification = db.relationship("Notification", back_populates="deliveries")
