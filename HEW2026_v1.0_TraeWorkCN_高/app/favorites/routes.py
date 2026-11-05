"""作品・オークションのお気に入り（要件定義書 5.8）。"""
from flask import Blueprint, abort, flash, redirect, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Artwork, ArtworkBookmark, Auction, Bookmark
from app.utils import safe_next

bp = Blueprint("favorites", __name__, url_prefix="/favorites")


@bp.route("/artwork/<int:artwork_id>", methods=["POST"])
@login_required
def toggle_artwork(artwork_id):
    artwork = db.session.get(Artwork, artwork_id)
    if artwork is None:
        abort(404)
    if artwork.status == "draft" and artwork.seller_id != current_user.id:
        abort(403)

    bookmark = (
        db.session.query(ArtworkBookmark)
        .filter(
            ArtworkBookmark.user_id == current_user.id,
            ArtworkBookmark.artwork_id == artwork.id,
        )
        .first()
    )
    if bookmark is None:
        db.session.add(
            ArtworkBookmark(user_id=current_user.id, artwork_id=artwork.id)
        )
        flash("作品をお気に入りに登録しました。", "success")
    else:
        db.session.delete(bookmark)
        flash("作品のお気に入りを解除しました。", "info")
    db.session.commit()

    default = (
        url_for("auctions.detail", auction_id=artwork.auction.id)
        if artwork.auction
        else url_for("account.index", tab="favorites_artworks")
    )
    return redirect(safe_next(default))


@bp.route("/auction/<int:auction_id>", methods=["POST"])
@login_required
def toggle_auction(auction_id):
    auction = db.session.get(Auction, auction_id)
    if auction is None or auction.artwork is None:
        abort(404)
    if auction.artwork.status not in {"listed", "sold"}:
        abort(404)

    bookmark = (
        db.session.query(Bookmark)
        .filter(
            Bookmark.user_id == current_user.id,
            Bookmark.auction_id == auction.id,
        )
        .first()
    )
    if bookmark is None:
        db.session.add(Bookmark(user_id=current_user.id, auction_id=auction.id))
        flash("オークションをお気に入りに登録しました。", "success")
    else:
        db.session.delete(bookmark)
        flash("オークションのお気に入りを解除しました。", "info")
    db.session.commit()

    default = url_for("auctions.detail", auction_id=auction.id)
    return redirect(safe_next(default))
