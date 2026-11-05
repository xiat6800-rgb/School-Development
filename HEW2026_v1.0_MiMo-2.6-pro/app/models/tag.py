from app.extensions import db


class Tag(db.Model):
    __tablename__ = "tags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now(),
        nullable=False,
    )


class ArtworkTag(db.Model):
    __tablename__ = "artwork_tags"
    __table_args__ = (
        db.UniqueConstraint("artwork_id", "tag_id", name="uq_artwork_tag"),
    )

    id = db.Column(db.Integer, primary_key=True)
    artwork_id = db.Column(
        db.Integer, db.ForeignKey("artworks.id"), nullable=False, index=True
    )
    tag_id = db.Column(
        db.Integer, db.ForeignKey("tags.id"), nullable=False, index=True
    )
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    artwork = db.relationship("Artwork", backref=db.backref("tag_links", lazy="dynamic"))
    tag = db.relationship("Tag", backref=db.backref("artwork_links", lazy="dynamic"))
