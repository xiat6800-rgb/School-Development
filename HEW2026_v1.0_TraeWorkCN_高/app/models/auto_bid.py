"""auto_bid_settings テーブル。"""
from app.extensions import db
from app.models.types import ID_TYPE
from app.utils import utcnow


class AutoBidSetting(db.Model):
    __tablename__ = "auto_bid_settings"
    __table_args__ = (
        db.UniqueConstraint("auction_id", "user_id", name="uq_auto_bid_auction_user"),
        db.Index("idx_auto_bid_active", "auction_id", "is_active"),
    )

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    auction_id = db.Column(
        ID_TYPE, db.ForeignKey("auctions.id"), nullable=False
    )
    user_id = db.Column(ID_TYPE, db.ForeignKey("users.id"), nullable=False)
    max_amount = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    auction = db.relationship("Auction", backref=db.backref("auto_bids", lazy="dynamic"))
    user = db.relationship("User", backref=db.backref("auto_bids", lazy="dynamic"))
