"""お気に入りモデル。作品とオークションを別テーブルで管理する。"""
from datetime import datetime, timezone

from ..extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ArtworkFavorite(db.Model):
    __tablename__ = "artwork_bookmarks"

    id = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'), primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)
    artwork_id = db.Column(db.BigInteger, db.ForeignKey("artworks.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    artwork = db.relationship("Artwork", backref="favorites")

    __table_args__ = (
        db.UniqueConstraint("user_id", "artwork_id", name="uq_artwork_favorite"),
    )


class AuctionFavorite(db.Model):
    __tablename__ = "bookmarks"

    id = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'), primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)
    auction_id = db.Column(db.BigInteger, db.ForeignKey("auctions.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    auction = db.relationship("Auction", backref="favorites")

    __table_args__ = (
        db.UniqueConstraint("user_id", "auction_id", name="uq_auction_favorite"),
    )
