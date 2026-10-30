"""お気に入りモデル。作品と競売を別テーブルで管理する。"""

from ..clock import utcnow
from ..extensions import db


class ArtworkFavorite(db.Model):
    """作品のお気に入り。"""

    __tablename__ = "artwork_bookmarks"
    __table_args__ = (
        db.UniqueConstraint("user_id", "artwork_id", name="uq_artwork_favorite"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    artwork_id = db.Column(
        db.Integer, db.ForeignKey("artworks.id"), nullable=False, index=True
    )
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User", backref=db.backref("artwork_favorites", lazy="dynamic"))
    artwork = db.relationship(
        "Artwork", backref=db.backref("favorited_by", lazy="dynamic")
    )


class AuctionFavorite(db.Model):
    """競売のお気に入り。"""

    __tablename__ = "bookmarks"
    __table_args__ = (
        db.UniqueConstraint("user_id", "auction_id", name="uq_auction_favorite"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    auction_id = db.Column(
        db.Integer, db.ForeignKey("auctions.id"), nullable=False, index=True
    )
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User", backref=db.backref("auction_favorites", lazy="dynamic"))
    auction = db.relationship(
        "Auction", backref=db.backref("favorited_by", lazy="dynamic")
    )
