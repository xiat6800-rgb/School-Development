"""アプリ内通知の模型。

メールは使用しない。通知は取引の確定後にだけ生成する。
"""

from __future__ import annotations

from app.extensions import db
from app.utils import utcnow

TYPE_BID_RECEIVED = "bid_received"
TYPE_PRICE_UPDATED = "price_updated"
TYPE_AUCTION_WON = "auction_won"
TYPE_AUCTION_LOST = "auction_lost"
TYPE_AUCTION_UNSOLD = "auction_unsold"
TYPE_AUTO_BID_STOPPED = "auto_bid_stopped"


class Notification(db.Model):
    """本人宛てのアプリ内通知。"""

    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    notification_type = db.Column(db.String(30), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    related_auction_id = db.Column(
        db.Integer, db.ForeignKey("auctions.id"), nullable=True, index=True
    )
    related_bid_id = db.Column(db.Integer, db.ForeignKey("bids.id"), nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True)
    revoked_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True
    )
    revoke_reason = db.Column(db.String(300), nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=utcnow, index=True
    )

    user = db.relationship(
        "User", backref="notifications", foreign_keys=[user_id]
    )
