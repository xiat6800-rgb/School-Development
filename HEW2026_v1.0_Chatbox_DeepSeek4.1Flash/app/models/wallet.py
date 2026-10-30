"""ポイント取引履歴モデル。"""

from ..clock import utcnow
from ..extensions import db


class WalletTransaction(db.Model):
    """残高の増減履歴。増加は正、減少は負で保存する。"""

    __tablename__ = "wallet_transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    transaction_type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    balance_after = db.Column(db.Integer, nullable=False)
    related_auction_id = db.Column(
        db.Integer, db.ForeignKey("auctions.id"), index=True
    )
    related_bid_id = db.Column(db.Integer, db.ForeignKey("bids.id"), index=True)
    memo = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    user = db.relationship("User", backref=db.backref("wallet_transactions", lazy="dynamic"))

    def __repr__(self):
        return f"<WalletTransaction {self.transaction_type} {self.amount}>"
