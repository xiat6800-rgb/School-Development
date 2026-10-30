"""bids テーブル（1オークションに複数入札を保存する）。"""
from app.extensions import db
from app.models.types import ID_TYPE
from app.utils import utcnow


class Bid(db.Model):
    __tablename__ = "bids"
    __table_args__ = (
        db.Index("idx_bids_auction_amount", "auction_id", "bid_amount", "created_at"),
        db.Index("idx_bids_bidder", "bidder_id", "created_at"),
    )

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    # 設計書の UNIQUE 制約は撤廃済み（要件定義書 10章の修正課題）
    auction_id = db.Column(
        ID_TYPE, db.ForeignKey("auctions.id"), nullable=False
    )
    bidder_id = db.Column(ID_TYPE, db.ForeignKey("users.id"), nullable=False)
    bid_amount = db.Column(db.Integer, nullable=False)
    is_auto_bid = db.Column(db.Boolean, nullable=False, default=False)
    bid_status = db.Column(
        db.Enum("accepted", "rejected", name="bid_status"), nullable=False
    )
    payment_intent_id = db.Column(
        ID_TYPE, db.ForeignKey("payment_intents.id"), nullable=True
    )
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    auction = db.relationship(
        "Auction", back_populates="bids", foreign_keys=[auction_id]
    )
    bidder = db.relationship("User", backref=db.backref("bids", lazy="dynamic"))

    def __repr__(self):
        return f"<Bid {self.id} {self.bid_amount}>"
