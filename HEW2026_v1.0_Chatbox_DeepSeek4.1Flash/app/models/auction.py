"""競売モデル。"""

from ..clock import utcnow
from ..constants import AUCTION_STATUS_ACTIVE, AUCTION_STATUS_ENDED
from ..extensions import db


class Auction(db.Model):
    """作品 1 件につき最大 1 件の競売。"""

    __tablename__ = "auctions"

    id = db.Column(db.Integer, primary_key=True)
    artwork_id = db.Column(
        db.Integer,
        db.ForeignKey("artworks.id"),
        nullable=False,
        unique=True,
    )
    start_price = db.Column(db.Integer, nullable=False, default=0)
    current_price = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(
        db.String(20), nullable=False, default=AUCTION_STATUS_ACTIVE, index=True
    )
    start_time = db.Column(db.DateTime, nullable=False, default=utcnow)
    end_time = db.Column(db.DateTime, nullable=False, index=True)
    winner_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    # 落札入札ID。bids との循環参照を避けるため外部キー制約は付けない。
    winner_bid_id = db.Column(db.Integer)
    final_price = db.Column(db.Integer)
    closed_reason = db.Column(db.String(20))
    closed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    artwork = db.relationship("Artwork", back_populates="auction")
    winner = db.relationship("User", foreign_keys=[winner_id])
    bids = db.relationship("Bid", back_populates="auction")

    @property
    def is_active(self):
        return self.status == AUCTION_STATUS_ACTIVE

    @property
    def is_ended(self):
        return self.status == AUCTION_STATUS_ENDED

    @property
    def seller_id(self):
        return self.artwork.artist_id if self.artwork else None

    def can_accept_bid(self, now):
        """開催中かつ終了日時前か。自動延長はしない。"""
        return self.is_active and now < self.end_time

    def is_seller(self, user):
        return bool(user) and getattr(user, "id", None) == self.seller_id

    def __repr__(self):
        return f"<Auction {self.id} price={self.current_price}>"
