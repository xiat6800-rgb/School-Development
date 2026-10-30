"""作品モデル。描画セッション・正式保存・公開状態を管理する。"""

from ..clock import utcnow
from ..constants import (
    ARTWORK_STATUS_DRAFT,
    ARTWORK_STATUS_LISTED,
    ARTWORK_STATUS_SOLD,
    ARTWORK_VISIBILITY_PUBLIC,
)
from ..extensions import db


class Artwork(db.Model):
    """サイト上で描いた作品。PNG とレイヤー ZIP の両方を保存して正式保存とする。"""

    __tablename__ = "artworks"

    id = db.Column(db.Integer, primary_key=True)
    artist_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    title = db.Column(db.String(200), nullable=False, default="")
    description = db.Column(db.Text)
    image_path = db.Column(db.String(500))
    layer_zip_path = db.Column(db.String(500))
    status = db.Column(
        db.String(20), nullable=False, default=ARTWORK_STATUS_DRAFT, index=True
    )
    visibility = db.Column(
        db.String(20), nullable=False, default=ARTWORK_VISIBILITY_PUBLIC
    )
    canvas_size = db.Column(db.Integer, nullable=False, default=1024)

    # 描画セッション（サーバー側で期限を管理する）
    drawing_duration_seconds = db.Column(db.Integer)
    drawing_started_at = db.Column(db.DateTime)
    drawing_deadline = db.Column(db.DateTime)
    drawing_finished_at = db.Column(db.DateTime)

    # 正式保存（PNG + ZIP）と保存猶予
    asset_saved_at = db.Column(db.DateTime)
    save_deadline = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    artist = db.relationship(
        "User", backref=db.backref("artworks", lazy="dynamic")
    )
    auction = db.relationship("Auction", back_populates="artwork", uselist=False)
    tags = db.relationship(
        "Tag",
        secondary="artwork_tags",
        back_populates="artworks",
        order_by="Tag.name",
    )

    @property
    def is_saved(self):
        """合成 PNG とレイヤー ZIP の両方が保存済みか。"""
        return bool(self.image_path) and bool(self.layer_zip_path)

    @property
    def is_public(self):
        return self.visibility == ARTWORK_VISIBILITY_PUBLIC

    @property
    def is_listed(self):
        return self.status == ARTWORK_STATUS_LISTED

    @property
    def is_sold(self):
        return self.status == ARTWORK_STATUS_SOLD

    def is_owned_by(self, user):
        return bool(user) and getattr(user, "id", None) == self.artist_id

    def can_accept_drawing(self, now):
        """まだ加筆できる描画セッションか。保存済みなら加筆不可。"""
        if self.is_saved:
            return False
        if self.drawing_deadline is None:
            return False
        return now < self.drawing_deadline

    def can_accept_assets(self, now):
        """固定データの再送を受け付けられるか（保存猶予 60 秒）。"""
        if self.is_saved:
            return False
        if self.save_deadline is None:
            return False
        return now <= self.save_deadline

    def is_visible_to(self, user):
        """閲覧権限。下書きは作者だけ、非公開作品は作者と管理者だけ。"""
        if self.is_public and self.status in (
            ARTWORK_STATUS_LISTED,
            ARTWORK_STATUS_SOLD,
        ):
            return True
        if self.is_owned_by(user):
            return True
        return bool(user) and user.is_authenticated and user.is_admin()

    def __repr__(self):
        return f"<Artwork {self.id} {self.title!r}>"
