from app.extensions import db


class Artwork(db.Model):
    __tablename__ = "artworks"

    STATUS_DRAFT = "draft"
    STATUS_LISTED = "listed"
    STATUS_SOLD = "sold"
    STATUS_CANCELLED = "cancelled"

    id = db.Column(db.Integer, primary_key=True)
    artist_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    title = db.Column(db.String(200), nullable=False, default="無題の作品")
    description = db.Column(db.Text, nullable=True)
    image_path = db.Column(db.String(500), nullable=True)
    layers_zip_path = db.Column(db.String(500), nullable=True)
    status = db.Column(
        db.String(20), nullable=False, default=STATUS_DRAFT, index=True
    )
    duration_seconds = db.Column(db.Integer, nullable=True)
    drawing_started_at = db.Column(db.DateTime, nullable=True)
    drawing_deadline = db.Column(db.DateTime, nullable=True)
    frozen_at = db.Column(db.DateTime, nullable=True)
    saved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now(),
        nullable=False,
    )

    artist = db.relationship("User", backref=db.backref("artworks", lazy="dynamic"))

    @property
    def is_formally_saved(self):
        return self.saved_at is not None

    @property
    def is_public(self):
        return self.status in (self.STATUS_LISTED, self.STATUS_SOLD)
