"""artworks テーブル。"""
from app.extensions import db
from app.models.tag import artwork_tags
from app.models.types import ID_TYPE
from app.utils import utcnow


class Artwork(db.Model):
    __tablename__ = "artworks"
    __table_args__ = (
        db.Index("idx_artworks_seller", "seller_id"),
        db.Index("idx_artworks_status", "status"),
    )

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    seller_id = db.Column(
        ID_TYPE, db.ForeignKey("users.id"), nullable=False
    )
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    # アップロード基準からの相対パス（実体は静的ディレクトリの外）
    image_path = db.Column(db.String(500), nullable=False)
    status = db.Column(
        db.Enum("draft", "listed", "sold", "cancelled", name="artwork_status"),
        nullable=False,
        default="draft",
    )
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    seller = db.relationship("User", backref=db.backref("artworks", lazy="dynamic"))
    auction = db.relationship("Auction", back_populates="artwork", uselist=False)
    tags = db.relationship(
        "Tag", secondary=artwork_tags, back_populates="artworks", lazy="select"
    )

    def is_public(self):
        return self.status in {"listed", "sold"}

    def __repr__(self):
        return f"<Artwork {self.id} {self.title}>"
