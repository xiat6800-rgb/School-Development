"""tags / artwork_tags。"""
from app.extensions import db
from app.models.types import ID_TYPE
from app.utils import utcnow

artwork_tags = db.Table(
    "artwork_tags",
    db.Column("id", ID_TYPE, primary_key=True, autoincrement=True),
    db.Column("artwork_id", ID_TYPE, db.ForeignKey("artworks.id"), nullable=False),
    db.Column("tag_id", ID_TYPE, db.ForeignKey("tags.id"), nullable=False),
    db.Column("created_at", db.DateTime, nullable=False, default=utcnow),
    db.UniqueConstraint("artwork_id", "tag_id", name="uq_artwork_tag"),
    db.Index("idx_artwork_tag_tag", "tag_id", "artwork_id"),
)


class Tag(db.Model):
    __tablename__ = "tags"

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    artworks = db.relationship(
        "Artwork", secondary=artwork_tags, back_populates="tags", lazy="dynamic"
    )

    def __repr__(self):
        return f"<Tag {self.name}>"
