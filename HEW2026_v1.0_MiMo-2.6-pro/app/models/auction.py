from app.extensions import db


class Auction(db.Model):
    __tablename__ = "auctions"

    STATUS_ACTIVE = "active"
    STATUS_ENDED = "ended"
    STATUS_CANCELLED = "cancelled"

    id = db.Column(db.Integer, primary_key=True)
    artwork_id = db.Column(
        db.Integer, db.ForeignKey("artworks.id"), nullable=False, index=True
    )
    start_price = db.Column(db.Integer, nullable=False)
    current_price = db.Column(db.Integer, nullable=False)
    status = db.Column(
        db.String(20), nullable=False, default=STATUS_ACTIVE, index=True
    )
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False, index=True)
    winner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    # 落札入札の参照。auctions ↔ bids の循環 FK を避けるため制約は
    # DB-deploy/deploy.sql（MariaDB）側で定義する。
    winner_bid_id = db.Column(db.Integer, nullable=True)
    final_price = db.Column(db.Integer, nullable=True)
    closed_reason = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now(),
        nullable=False,
    )

    artwork = db.relationship("Artwork", backref=db.backref("auctions", lazy="dynamic"))
    winner = db.relationship("User", foreign_keys=[winner_id])

    @property
    def is_open(self):
        return self.status == self.STATUS_ACTIVE


class Bid(db.Model):
    __tablename__ = "bids"

    STATUS_ACCEPTED = "accepted"
    STATUS_REJECTED = "rejected"

    id = db.Column(db.Integer, primary_key=True)
    auction_id = db.Column(
        db.Integer, db.ForeignKey("auctions.id"), nullable=False, index=True
    )
    bidder_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    bid_amount = db.Column(db.Integer, nullable=False)
    is_auto_bid = db.Column(db.Boolean, nullable=False, default=False)
    bid_status = db.Column(db.String(20), nullable=False, default=STATUS_ACCEPTED)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    auction = db.relationship(
        "Auction",
        foreign_keys=[auction_id],
        backref=db.backref("bids", lazy="dynamic"),
    )
    bidder = db.relationship("User", backref=db.backref("bids", lazy="dynamic"))


class AutoBidSetting(db.Model):
    __tablename__ = "auto_bid_settings"
    __table_args__ = (
        db.UniqueConstraint("auction_id", "user_id", name="uq_auto_bid_auction_user"),
    )

    id = db.Column(db.Integer, primary_key=True)
    auction_id = db.Column(
        db.Integer, db.ForeignKey("auctions.id"), nullable=False, index=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    max_amount = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now(),
        nullable=False,
    )

    auction = db.relationship(
        "Auction", backref=db.backref("auto_bid_settings", lazy="dynamic")
    )
    user = db.relationship(
        "User", backref=db.backref("auto_bid_settings", lazy="dynamic")
    )
