"""wallet_transactions テーブル。"""
from app.extensions import db
from app.models.types import ID_TYPE
from app.utils import utcnow


class WalletTransaction(db.Model):
    __tablename__ = "wallet_transactions"
    __table_args__ = (
        db.Index("idx_wallet_user_created", "user_id", "created_at"),
        db.Index("idx_wallet_auction", "related_auction_id"),
        db.Index("idx_wallet_bid", "related_bid_id"),
    )

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    user_id = db.Column(ID_TYPE, db.ForeignKey("users.id"), nullable=False)
    transaction_type = db.Column(
        db.Enum(
            "charge", "bid", "refund", "purchase", "bonus", name="transaction_type"
        ),
        nullable=False,
    )
    # 増加は正、減少は負
    amount = db.Column(db.Integer, nullable=False)
    balance_after = db.Column(db.Integer, nullable=False)
    related_auction_id = db.Column(
        ID_TYPE, db.ForeignKey("auctions.id"), nullable=True
    )
    related_bid_id = db.Column(
        ID_TYPE, db.ForeignKey("bids.id"), nullable=True
    )
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship(
        "User", backref=db.backref("wallet_transactions", lazy="dynamic")
    )
    auction = db.relationship("Auction", backref=db.backref("wallet_transactions", lazy="dynamic"))
    bid = db.relationship("Bid", backref=db.backref("wallet_transactions", lazy="dynamic"))
