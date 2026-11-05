"""自動入札設定モデル。"""
from datetime import datetime, timezone

from ..extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AutoBidSetting(db.Model):
    __tablename__ = "auto_bid_settings"

    id = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'), primary_key=True, autoincrement=True)
    auction_id = db.Column(
        db.BigInteger, db.ForeignKey("auctions.id"), nullable=False
    )
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)
    max_amount = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    auction = db.relationship("Auction", backref="auto_bid_settings")
    user = db.relationship("User", backref="auto_bid_settings")

    __table_args__ = (
        db.UniqueConstraint("auction_id", "user_id", name="uq_auto_bid_auction_user"),
        db.Index("idx_auto_bid_auction_active", "auction_id", "is_active"),
    )
