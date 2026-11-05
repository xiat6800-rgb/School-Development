"""auctions テーブル。"""
from app.extensions import db
from app.models.types import ID_TYPE
from app.utils import utcnow


class Auction(db.Model):
    __tablename__ = "auctions"
    __table_args__ = (
        db.Index("idx_auctions_status_end", "status", "end_time"),
        db.Index("idx_auctions_winner", "winner_id"),
    )

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    artwork_id = db.Column(
        ID_TYPE,
        db.ForeignKey("artworks.id"),
        nullable=False,
        unique=True,
    )
    start_price = db.Column(db.Integer, nullable=False)
    current_price = db.Column(db.Integer, nullable=False)
    # Ver0.5 では落札判定に使わない（要件定義書 6章）
    reserve_price = db.Column(db.Integer, nullable=True)
    status = db.Column(
        db.Enum("active", "ended", "cancelled", name="auction_status"),
        nullable=False,
        default="active",
    )
    start_time = db.Column(db.DateTime, nullable=False, default=utcnow)
    end_time = db.Column(db.DateTime, nullable=False)
    winner_id = db.Column(ID_TYPE, db.ForeignKey("users.id"), nullable=True)
    # bids(id) への外部キー。bids → auctions と循環するため use_alter で追加する
    winner_bid_id = db.Column(
        ID_TYPE,
        db.ForeignKey("bids.id", use_alter=True, name="fk_auctions_winner_bid"),
        nullable=True,
        unique=True,
    )
    final_price = db.Column(db.Integer, nullable=True)
    closed_reason = db.Column(
        db.Enum(
            "time_expired",
            "seller_finished",
            "cancelled",
            name="auction_closed_reason",
        ),
        nullable=True,
    )
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    artwork = db.relationship(
        "Artwork", back_populates="auction", foreign_keys=[artwork_id]
    )
    winner = db.relationship("User", foreign_keys=[winner_id])
    winner_bid = db.relationship(
        "Bid",
        primaryjoin="Auction.winner_bid_id == Bid.id",
        foreign_keys="Auction.winner_bid_id",
        uselist=False,
        post_update=True,
    )
    bids = db.relationship(
        "Bid",
        back_populates="auction",
        foreign_keys="Bid.auction_id",
        order_by="Bid.created_at.asc()",
        lazy="select",
    )

    @property
    def seller_id(self):
        return self.artwork.seller_id if self.artwork else None

    @property
    def is_active(self):
        return self.status == "active" and self.end_time > utcnow()

    def highest_bid(self):
        accepted = [b for b in self.bids if b.bid_status == "accepted"]
        if not accepted:
            return None
        return sorted(accepted, key=lambda b: (-b.bid_amount, b.created_at))[0]

    def __repr__(self):
        return f"<Auction {self.id} artwork={self.artwork_id}>"
