"""タグモデルと作品-タグ中間テーブル。"""
from datetime import datetime, timezone

from ..extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


artwork_tags = db.Table(
    "artwork_tags",
    db.Column(
        "artwork_id", db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey("artworks.id"), primary_key=True
    ),
    db.Column("tag_id", db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey("tags.id"), primary_key=True),
    db.Column("created_at", db.DateTime, nullable=False, default=utcnow),
)


class Tag(db.Model):
    __tablename__ = "tags"

    id = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'), primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
