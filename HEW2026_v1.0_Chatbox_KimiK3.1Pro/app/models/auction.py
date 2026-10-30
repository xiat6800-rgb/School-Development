from app.extensions import db
from app.utils import utcnow


class Auction(db.Model):
    __tablename__ = "auctions"

    id = db.Column(db.Integer, primary_key=True)
    artwork_id = db.Column(db.Integer, db.ForeignKey("artworks.id"), nullable=False)
    start_price = db.Column(db.Integer, nullable=False)
    current_price = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="active", index=True)
    starts_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    ends_at = db.Column(db.DateTime, nullable=False, index=True)
    current_bid_id = db.Column(
        db.Integer, db.ForeignKey("bids.id", use_alter=True), nullable=True
    )
    winner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    winner_bid_id = db.Column(
        db.Integer, db.ForeignKey("bids.id", use_alter=True), nullable=True
    )
    final_price = db.Column(db.Integer, nullable=True)
    settled_at = db.Column(db.DateTime, nullable=True)
    cancelled_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    cancellation_reason = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    artwork = db.relationship("Artwork", back_populates="auctions")
    bids = db.relationship(
        "Bid", back_populates="auction", foreign_keys="Bid.auction_id",
        order_by="Bid.id.desc()", lazy="dynamic"
    )
    auto_bids = db.relationship(
        "AutoBid", back_populates="auction", lazy="dynamic"
    )
    current_bid = db.relationship(
        "Bid", foreign_keys=[current_bid_id], post_update=True
    )
    winner_bid = db.relationship("Bid", foreign_keys=[winner_bid_id])
    winner = db.relationship("User", foreign_keys=[winner_id])
    cancelled_by = db.relationship("User", foreign_keys=[cancelled_by_id])

    @property
    def seller(self):
        return self.artwork.artist


class Bid(db.Model):
    __tablename__ = "bids"

    id = db.Column(db.Integer, primary_key=True)
    auction_id = db.Column(db.Integer, db.ForeignKey("auctions.id"), nullable=False)
    bidder_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    held_amount = db.Column(db.Integer, nullable=False)
    is_auto = db.Column(db.Boolean, nullable=False, default=False)
    refunded_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    auction = db.relationship(
        "Auction", back_populates="bids", foreign_keys=[auction_id]
    )
    bidder = db.relationship("User")


class AutoBid(db.Model):
    __tablename__ = "auto_bid_settings"
    __table_args__ = (
        db.UniqueConstraint("auction_id", "user_id", name="uq_auto_bid_user"),
    )

    id = db.Column(db.Integer, primary_key=True)
    auction_id = db.Column(db.Integer, db.ForeignKey("auctions.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    max_amount = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    auction = db.relationship("Auction", back_populates="auto_bids")
    user = db.relationship("User")


class AuctionFavorite(db.Model):
    __tablename__ = "auction_favorites"
    __table_args__ = (
        db.UniqueConstraint("user_id", "auction_id", name="uq_auction_favorite"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    auction_id = db.Column(db.Integer, db.ForeignKey("auctions.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User")
    auction = db.relationship("Auction")
