"""入札モデル。同一競売へ複数の入札履歴を保存する。"""

from ..clock import utcnow
from ..constants import BID_STATUS_ACCEPTED
from ..extensions import db


class Bid(db.Model):
    """受理した入札。入札時にポイントを差し引く。"""

    __tablename__ = "bids"

    id = db.Column(db.Integer, primary_key=True)
    auction_id = db.Column(
        db.Integer,
        db.ForeignKey("auctions.id"),
        nullable=False,
        index=True,
    )
    bidder_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    bid_amount = db.Column(db.Integer, nullable=False)
    is_auto_bid = db.Column(db.Boolean, nullable=False, default=False)
    bid_status = db.Column(
        db.String(20), nullable=False, default=BID_STATUS_ACCEPTED
    )
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    auction = db.relationship("Auction", back_populates="bids")
    bidder = db.relationship("User", backref=db.backref("bids", lazy="dynamic"))

    def __repr__(self):
        return f"<Bid {self.id} {self.bid_amount} by {self.bidder_id}>"
