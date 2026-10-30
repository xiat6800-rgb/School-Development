from app.extensions import db
from app.utils import utcnow


artwork_tags = db.Table(
    "artwork_tags",
    db.Column(
        "artwork_id", db.Integer, db.ForeignKey("artworks.id"), primary_key=True
    ),
    db.Column("tag_id", db.Integer, db.ForeignKey("tags.id"), primary_key=True),
    db.Column("created_at", db.DateTime, nullable=False, default=utcnow),
)


class Artwork(db.Model):
    __tablename__ = "artworks"

    id = db.Column(db.Integer, primary_key=True)
    artist_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False, default="無題")
    description = db.Column(db.Text, nullable=False, default="")
    image_path = db.Column(db.String(500), nullable=True)
    archive_path = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="draft", index=True)
    is_public = db.Column(db.Boolean, nullable=False, default=False)
    visibility_reason = db.Column(db.String(500), nullable=True)
    visibility_updated_at = db.Column(db.DateTime, nullable=True)
    drawing_started_at = db.Column(db.DateTime, nullable=False)
    drawing_ends_at = db.Column(db.DateTime, nullable=False, index=True)
    finished_at = db.Column(db.DateTime, nullable=True)
    save_grace_ends_at = db.Column(db.DateTime, nullable=True)
    saved_at = db.Column(db.DateTime, nullable=True)
    duration_seconds = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    artist = db.relationship("User", back_populates="artworks")
    auctions = db.relationship(
        "Auction", back_populates="artwork", order_by="Auction.id.desc()"
    )
    tags = db.relationship("Tag", secondary=artwork_tags, back_populates="artworks")
    stream = db.relationship("LiveStream", back_populates="artwork", uselist=False)

    @property
    def is_saved(self):
        return bool(self.image_path and self.archive_path and self.saved_at)

    @property
    def active_auction(self):
        return next((a for a in self.auctions if a.status == "active"), None)

    @property
    def latest_auction(self):
        return self.auctions[0] if self.auctions else None


class Tag(db.Model):
    __tablename__ = "tags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    artworks = db.relationship(
        "Artwork", secondary=artwork_tags, back_populates="tags"
    )


class ArtworkFavorite(db.Model):
    __tablename__ = "artwork_favorites"
    __table_args__ = (
        db.UniqueConstraint("user_id", "artwork_id", name="uq_artwork_favorite"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    artwork_id = db.Column(db.Integer, db.ForeignKey("artworks.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User")
    artwork = db.relationship("Artwork")
