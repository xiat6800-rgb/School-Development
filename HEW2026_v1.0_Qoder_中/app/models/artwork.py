"""作品（下書き）モデル。画像なし下書きと正式保存完了を管理する。"""
from datetime import datetime, timezone

from ..extensions import db
from .tag import artwork_tags


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Artwork(db.Model):
    __tablename__ = "artworks"

    id = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'), primary_key=True, autoincrement=True)
    artist_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id"), nullable=False, index=True
    )
    title = db.Column(db.String(200), nullable=False, default="")
    description = db.Column(db.Text, nullable=True)
    # 正式保存成功までは NULL（画像なし下書き）
    image_path = db.Column(db.String(500), nullable=True)
    layer_zip_path = db.Column(db.String(500), nullable=True)
    # draft / listed / sold / cancelled
    status = db.Column(db.String(20), nullable=False, default="draft", index=True)

    # 描画セッション（開始時刻・期限はサーバー管理。開始後変更不可）
    drawing_duration_seconds = db.Column(db.Integer, nullable=True)
    drawing_started_at = db.Column(db.DateTime, nullable=True)
    drawing_deadline = db.Column(db.DateTime, nullable=True)
    drawing_saved_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    tags = db.relationship("Tag", secondary=artwork_tags, backref="artworks")
    artist = db.relationship("User", backref="artworks")

    @property
    def is_saved(self):
        """PNG とレイヤーZIP の両方が保存済みか（正式保存成功）。"""
        return bool(self.image_path and self.layer_zip_path and self.drawing_saved_at)

    @property
    def is_public(self):
        return self.status in ("listed", "sold", "cancelled")
