"""お気に入りの模型。

作品のお気に入り（artwork_bookmarks）とオークションのお気に入り
（bookmarks）は別テーブルで管理し、対象を混在させない。
"""

from __future__ import annotations

from app.extensions import db
from app.utils import utcnow


class ArtworkFavorite(db.Model):
    """作品のお気に入り登録。"""

    __tablename__ = "artwork_bookmarks"
    __table_args__ = (
        db.UniqueConstraint("user_id", "artwork_id", name="uq_artwork_bookmark"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    artwork_id = db.Column(
        db.Integer, db.ForeignKey("artworks.id"), nullable=False, index=True
    )
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    artwork = db.relationship("Artwork", backref="favorite_links")


class AuctionFavorite(db.Model):
    """オークションのお気に入り登録。"""

    __tablename__ = "bookmarks"
    __table_args__ = (
        db.UniqueConstraint("user_id", "auction_id", name="uq_auction_bookmark"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    auction_id = db.Column(
        db.Integer, db.ForeignKey("auctions.id"), nullable=False, index=True
    )
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    auction = db.relationship("Auction", backref="favorite_links")
