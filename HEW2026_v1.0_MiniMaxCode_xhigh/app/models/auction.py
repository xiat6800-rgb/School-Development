"""オークション（競売）の模型。

1 作品につき開催中のオークションは高々 1 件。取消後に再出品すると
競売行は履歴として残り、``active_slot`` が NULL の行が過去分になる。
落札者は終了確定時に記録する。
"""

from __future__ import annotations

from app.extensions import db
from app.utils import utcnow

ACTIVE = "active"
ENDED = "ended"
CANCELLED = "cancelled"

REASON_TIME_EXPIRED = "time_expired"
REASON_SELLER_CANCELLED = "seller_cancelled"
REASON_ADMIN_CANCELLED = "admin_cancelled"
REASON_HIDDEN = "hidden"

# 開催中のときだけ 1 が入る。MySQL の UNIQUE 制約は NULL 同士を
# 衝突させないので、UNIQUE (artwork_id, active_slot) により
# 「同一作品で同時開催の競売は高々 1 件」が DB で保証される。
ACTIVE_SLOT = 1


class Auction(db.Model):
    """作品の競売。"""

    __tablename__ = "auctions"
    __table_args__ = (
        db.UniqueConstraint(
            "artwork_id", "active_slot", name="uq_auctions_artwork_active_slot"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    artwork_id = db.Column(
        db.Integer, db.ForeignKey("artworks.id"), nullable=False, index=True
    )
    start_price = db.Column(db.Integer, nullable=False, default=0)
    current_price = db.Column(db.Integer, nullable=False, default=0)
    reserve_price = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), nullable=False, default=ACTIVE, index=True)
    active_slot = db.Column(db.Integer, nullable=True, default=ACTIVE_SLOT)
    previous_auction_id = db.Column(
        db.Integer, db.ForeignKey("auctions.id"), nullable=True, index=True
    )
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
