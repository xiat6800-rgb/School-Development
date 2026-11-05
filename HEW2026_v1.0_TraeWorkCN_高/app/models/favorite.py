"""bookmarks（オークション）と artwork_bookmarks（作品）。"""
from app.extensions import db
from app.models.types import ID_TYPE
from app.utils import utcnow


class Bookmark(db.Model):
    __tablename__ = "bookmarks"
    __table_args__ = (
        db.UniqueConstraint("user_id", "auction_id", name="uq_bookmark_user_auction"),
        db.Index("idx_bookmarks_auction", "auction_id"),
    )

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    user_id = db.Column(ID_TYPE, db.ForeignKey("users.id"), nullable=False)
    auction_id = db.Column(
        ID_TYPE, db.ForeignKey("auctions.id"), nullable=False
    )
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User", backref=db.backref("bookmarks", lazy="dynamic"))
    auction = db.relationship(
        "Auction", backref=db.backref("bookmarks", lazy="dynamic")
    )


class ArtworkBookmark(db.Model):
    __tablename__ = "artwork_bookmarks"
    __table_args__ = (
        db.UniqueConstraint(
            "user_id", "artwork_id", name="uq_artwork_bookmark_user_artwork"
        ),
        db.Index("idx_artwork_bookmarks_artwork", "artwork_id"),
    )

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    user_id = db.Column(ID_TYPE, db.ForeignKey("users.id"), nullable=False)
    artwork_id = db.Column(
        ID_TYPE, db.ForeignKey("artworks.id"), nullable=False
    )
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship(
        "User", backref=db.backref("artwork_bookmarks", lazy="dynamic")
    )
    artwork = db.relationship(
        "Artwork", backref=db.backref("bookmarks", lazy="dynamic")
    )
