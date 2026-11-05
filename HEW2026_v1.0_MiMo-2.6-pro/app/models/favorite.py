from app.extensions import db


class Bookmark(db.Model):
    """オークションのお気に入り。作品用は ArtworkBookmark。"""

    __tablename__ = "bookmarks"
    __table_args__ = (
        db.UniqueConstraint("user_id", "auction_id", name="uq_bookmark_user_auction"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    auction_id = db.Column(
        db.Integer, db.ForeignKey("auctions.id"), nullable=False, index=True
    )
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    user = db.relationship("User", backref=db.backref("bookmarks", lazy="dynamic"))
    auction = db.relationship(
        "Auction", backref=db.backref("bookmarks", lazy="dynamic")
    )


class ArtworkBookmark(db.Model):
    __tablename__ = "artwork_bookmarks"
    __table_args__ = (
        db.UniqueConstraint("user_id", "artwork_id", name="uq_abm_user_artwork"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    artwork_id = db.Column(
        db.Integer, db.ForeignKey("artworks.id"), nullable=False, index=True
    )
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    user = db.relationship(
        "User", backref=db.backref("artwork_bookmarks", lazy="dynamic")
    )
    artwork = db.relationship(
        "Artwork", backref=db.backref("bookmarks", lazy="dynamic")
    )
