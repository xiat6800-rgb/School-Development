"""入札履歴モデル。同一オークションへの複数入札を履歴として保存する。"""
from datetime import datetime, timezone

from ..extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Bid(db.Model):
    __tablename__ = "bids"

    id = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'), primary_key=True, autoincrement=True)
    auction_id = db.Column(
        db.BigInteger, db.ForeignKey("auctions.id"), nullable=False, index=True
    )
    bidder_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id"), nullable=False, index=True
    )
    bid_amount = db.Column(db.Integer, nullable=False)
    is_auto_bid = db.Column(db.Boolean, nullable=False, default=False)
    # accepted / rejected（受理した入札のみ保存する運用）
    bid_status = db.Column(db.String(10), nullable=False, default="accepted")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    auction = db.relationship("Auction", backref=db.backref("bids", order_by="Bid.created_at"))
    bidder = db.relationship("User", backref="bids")

    __table_args__ = (
        db.Index("idx_bids_auction_amount_created", "auction_id", "bid_amount", "created_at"),
    )
