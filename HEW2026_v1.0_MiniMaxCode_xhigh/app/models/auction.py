"""オークション（競売）の模型。

Ver0.5 では 1 作品につき 1 オークション。落札者は終了確定時に記録する。
"""

from __future__ import annotations

from app.extensions import db
from app.utils import utcnow

ACTIVE = "active"
ENDED = "ended"

REASON_TIME_EXPIRED = "time_expired"


class Auction(db.Model):
    """作品の競売。"""

    __tablename__ = "auctions"

    id = db.Column(db.Integer, primary_key=True)
    artwork_id = db.Column(
        db.Integer, db.ForeignKey("artworks.id"), nullable=False, unique=True
    )
    start_price = db.Column(db.Integer, nullable=False, default=0)
    current_price = db.Column(db.Integer, nullable=False, default=0)
    reserve_price = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), nullable=False, default=ACTIVE, index=True)
    start_time = db.Column(db.DateTime, nullable=False, default=utcnow)
    end_time = db.Column(db.DateTime, nullable=False, index=True)
    winner_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True
    )
    winner_bid_id = db.Column(
        db.Integer,
        db.ForeignKey("bids.id", use_alter=True, name="fk_auctions_winner_bid"),
        nullable=True,
    )
    final_price = db.Column(db.Integer, nullable=True)
    closed_reason = db.Column(db.String(30), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    winner = db.relationship("User", foreign_keys=[winner_id])
    bids = db.relationship(
        "Bid",
        backref="auction",
        order_by="Bid.created_at",
        lazy="selectin",
        foreign_keys="Bid.auction_id",
    )

    @property
    def is_active(self) -> bool:
        """開催中かどうかを返す。"""
        return self.status == ACTIVE

    @property
    def has_winner(self) -> bool:
        """落札者が確定しているかを返す。"""
        return self.winner_id is not None

    def accepted_bids(self) -> list:
        """受理済みの入札を金額降順（同額は先着順）で返す。"""
        accepted = [bid for bid in self.bids if bid.bid_status == "accepted"]
        accepted.sort(key=lambda bid: (-bid.bid_amount, bid.created_at, bid.id))
        return accepted

    def top_bid(self):
        """現在の最高入札を返す。入札がなければ None。"""
        accepted = self.accepted_bids()
        return accepted[0] if accepted else None

    def __repr__(self) -> str:  # pragma: no cover - デバッグ用
        return f"<Auction {self.id} {self.status} {self.current_price}>"
