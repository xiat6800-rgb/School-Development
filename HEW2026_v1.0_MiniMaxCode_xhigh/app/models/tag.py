"""タグの模型と作品とタグの中間テーブル。"""

from __future__ import annotations

from app.extensions import db
from app.utils import utcnow


class Tag(db.Model):
    """作品の分類・検索に使うタグマスタ。"""

    __tablename__ = "tags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def __repr__(self) -> str:  # pragma: no cover - デバッグ用
        return f"<Tag {self.id} {self.name}>"


class ArtworkTag(db.Model):
    """作品とタグの中間テーブル。同一タグの重複付与は禁止。"""

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
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    tag = db.relationship("Tag", backref="artwork_links")
