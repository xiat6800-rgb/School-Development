"""作品と描画セッションの模型。

- 作品（Artwork）: 下書き ``draft`` → 出品 ``listed`` → 落札 ``sold``
  （取消 ``cancelled`` / 管理者の非公開化 ``hidden`` も持つ）
- 描画セッション（DrawingSession）: 開始時刻・期限・保存猶予をサーバー管理
"""

from __future__ import annotations

from app.extensions import db
from app.models.auction import ACTIVE
from app.utils import utcnow

DRAFT = "draft"
LISTED = "listed"
SOLD = "sold"
CANCELLED = "cancelled"
HIDDEN = "hidden"


class Artwork(db.Model):
    """ 作者が描いた作品。"""

    __tablename__ = "artworks"

    id = db.Column(db.Integer, primary_key=True)
    artist_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    title = db.Column(db.String(200), nullable=False, default="")
    description = db.Column(db.Text, nullable=True)
    image_path = db.Column(db.String(500), nullable=True)
    layer_archive_path = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(20), nullable=False, default=DRAFT, index=True)
    hidden_reason = db.Column(db.String(300), nullable=True)
    hidden_at = db.Column(db.DateTime, nullable=True)
    hidden_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True
    )
    save_completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    artist = db.relationship(
        "User", backref="artworks", foreign_keys=[artist_id]
    )
    drawing_session = db.relationship(
        "DrawingSession",
        backref="artwork",
        uselist=False,
        cascade="all, delete-orphan",
    )
    auction = db.relationship(
        "Auction", backref="artwork", cascade="all, delete-orphan"
    )
    tag_links = db.relationship(
        "ArtworkTag", backref="artwork", cascade="all, delete-orphan"
    )
    tags = db.relationship(
        "Tag",
        secondary="artwork_tags",
        backref="artworks",
        lazy="selectin",
        viewonly=True,
    )

    @property
    def active_auction(self):
        """開催中の競売を返す。なければ None。"""
        for auction in self.auction:
            if auction.status == ACTIVE:
                return auction
        return None

    @property
    def is_hidden(self) -> bool:
        """管理者によって非公開化された作品かどうかを返す。"""
        return self.status == HIDDEN

    @property
    def is_public(self) -> bool:
        """公開状態（draft 以外）かどうかを返す。"""
        return self.status != DRAFT

    @property
    def is_saved(self) -> bool:
        """正式保存（PNG とレイヤー ZIP の保存完了）済みかどうかを返す。"""
        return self.save_completed_at is not None and bool(self.image_path)

    def __repr__(self) -> str:  # pragma: no cover - デバッグ用
        return f"<Artwork {self.id} {self.status}>"


class DrawingSession(db.Model):
    """描画の開始・期限・保存猶予を管理するセッション。

    開始後の変更は不可とし、期限はサーバー側で管理する。
    """

    __tablename__ = "drawing_sessions"

    id = db.Column(db.Integer, primary_key=True)
    artwork_id = db.Column(
        db.Integer, db.ForeignKey("artworks.id"), nullable=False, unique=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    duration_seconds = db.Column(db.Integer, nullable=False)
    started_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    deadline_at = db.Column(db.DateTime, nullable=False)
    finished_at = db.Column(db.DateTime, nullable=True)
    save_grace_until = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="active")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def __repr__(self) -> str:  # pragma: no cover - デバッグ用
        return f"<DrawingSession {self.id} {self.status}>"
