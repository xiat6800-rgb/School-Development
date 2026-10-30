"""自動入札の設定モデル。"""

from ..clock import utcnow
from ..extensions import db


class AutoBidSetting(db.Model):
    """利用者ごと・競売ごとの自動入札上限額。"""

    __tablename__ = "auto_bid_settings"
    __table_args__ = (
        db.UniqueConstraint("auction_id", "user_id", name="uq_auto_bid_user"),
    )

    id = db.Column(db.Integer, primary_key=True)
    auction_id = db.Column(
        db.Integer,
        db.ForeignKey("auctions.id"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    max_amount = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    auction = db.relationship("Auction", backref=db.backref("auto_bids", lazy="dynamic"))
    user = db.relationship("User", backref=db.backref("auto_bids", lazy="dynamic"))

    def __repr__(self):
        return f"<AutoBidSetting {self.auction_id}/{self.user_id} max={self.max_amount}>"
