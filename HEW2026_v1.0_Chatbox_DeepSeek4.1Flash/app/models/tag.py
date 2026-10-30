"""タグと作品タグの中間テーブル。"""

from ..clock import utcnow
from ..extensions import db

artwork_tags = db.Table(
    "artwork_tags",
    db.Column("id", db.Integer, primary_key=True),
    db.Column(
        "artwork_id",
        db.Integer,
        db.ForeignKey("artworks.id"),
        nullable=False,
        index=True,
    ),
    db.Column(
        "tag_id", db.Integer, db.ForeignKey("tags.id"), nullable=False, index=True
    ),
    db.Column("created_at", db.DateTime, nullable=False, default=utcnow),
    db.UniqueConstraint("artwork_id", "tag_id", name="uq_artwork_tag"),
)


class Tag(db.Model):
    """作品の分類・検索に使用するタグ。"""

    __tablename__ = "tags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    artworks = db.relationship(
        "Artwork",
        secondary=artwork_tags,
        back_populates="tags",
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<Tag {self.name}>"
