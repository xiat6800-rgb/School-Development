from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Artwork, ArtworkBookmark, Auction, Bookmark

bp = Blueprint("favorites", __name__)


@bp.route("/artworks/<int:artwork_id>/favorite/add", methods=["POST"])
@login_required
def add_artwork_favorite(artwork_id):
    artwork = db.session.get(Artwork, artwork_id)
    if artwork is None or not artwork.is_public:
        abort(404)
    exists = ArtworkBookmark.query.filter_by(
        user_id=current_user.id, artwork_id=artwork.id
    ).first()
    if exists is None:
        db.session.add(
            ArtworkBookmark(user_id=current_user.id, artwork_id=artwork.id)
        )
        db.session.commit()
        flash("作品をお気に入りに登録しました。", "success")
    return redirect(url_for("index"))


@bp.route("/artworks/<int:artwork_id>/favorite/remove", methods=["POST"])
@login_required
def remove_artwork_favorite(artwork_id):
    ArtworkBookmark.query.filter_by(
        user_id=current_user.id, artwork_id=artwork_id
    ).delete()
    db.session.commit()
    flash("作品のお気に入りを解除しました。", "success")
    return redirect(url_for("favorites.list_artwork_favorites"))


@bp.route("/auctions/<int:auction_id>/favorite/add", methods=["POST"])
@login_required
def add_auction_favorite(auction_id):
    auction = db.session.get(Auction, auction_id)
    if auction is None:
        abort(404)
    exists = Bookmark.query.filter_by(
        user_id=current_user.id, auction_id=auction.id
    ).first()
    if exists is None:
        db.session.add(Bookmark(user_id=current_user.id, auction_id=auction.id))
        db.session.commit()
        flash("オークションをお気に入りに登録しました。", "success")
    return redirect(url_for("auctions.show_auction_detail", auction_id=auction.id))


@bp.route("/auctions/<int:auction_id>/favorite/remove", methods=["POST"])
@login_required
def remove_auction_favorite(auction_id):
    Bookmark.query.filter_by(
        user_id=current_user.id, auction_id=auction_id
    ).delete()
    db.session.commit()
    flash("オークションのお気に入りを解除しました。", "success")
    return redirect(url_for("favorites.list_auction_favorites"))


@bp.route("/account/favorites/artworks", methods=["GET"])
@login_required
def list_artwork_favorites():
    favorites = (
        ArtworkBookmark.query.filter_by(user_id=current_user.id)
        .order_by(ArtworkBookmark.created_at.desc())
        .all()
    )
    return render_template("favorites/artworks.html", favorites=favorites)


@bp.route("/account/favorites/auctions", methods=["GET"])
@login_required
def list_auction_favorites():
    favorites = (
        Bookmark.query.filter_by(user_id=current_user.id)
        .order_by(Bookmark.created_at.desc())
        .all()
    )
    return render_template("favorites/auctions.html", favorites=favorites)
