"""入札の模型。

同一オークションへの複数入札を履歴として保存する
（db設計 5.2 / 要件 5.4 の運用方針に従い auction_id に一意制約を設けない）。
"""

from __future__ import annotations

from app.extensions import db
from app.utils import utcnow

ACCEPTED = "accepted"
REJECTED = "rejected"


class Bid(db.Model):
    """1 件の入札履歴。"""

    __tablename__ = "bids"

    id = db.Column(db.Integer, primary_key=True)
    auction_id = db.Column(
        db.Integer, db.ForeignKey("auctions.id"), nullable=False, index=True
    )
    bidder_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    bid_amount = db.Column(db.Integer, nullable=False)
    is_auto_bid = db.Column(db.Boolean, nullable=False, default=False)
    bid_status = db.Column(db.String(20), nullable=False, default=ACCEPTED)
    created_at = db.Column(
        db.DateTime, nullable=False, default=utcnow, index=True
    )

    bidder = db.relationship("User", backref="bids")

    @property
    def is_accepted(self) -> bool:
        """受理済みの入札かどうかを返す。"""
        return self.bid_status == ACCEPTED

    def __repr__(self) -> str:  # pragma: no cover - デバッグ用
        return f"<Bid {self.id} {self.bid_amount} {self.bid_status}>"
