"""お気に入り登録・解除のルート。作品とオークションを別々に扱う。"""
from flask import abort, flash, redirect, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models.artwork import Artwork
from ..models.auction import Auction
from ..models.favorite import ArtworkFavorite, AuctionFavorite
from . import bp


@bp.route("/favorites/artworks/<int:artwork_id>/add", methods=["POST"])
@login_required
def add_artwork_favorite(artwork_id):
    artwork = db.session.get(Artwork, artwork_id)
    if artwork is None or not artwork.is_public:
        abort(404)
    exists = ArtworkFavorite.query.filter_by(
        user_id=current_user.id, artwork_id=artwork_id
    ).first()
    if exists is None:
        db.session.add(ArtworkFavorite(user_id=current_user.id, artwork_id=artwork_id))
        db.session.commit()
        flash("作品をお気に入りに登録しました。", "info")
    return redirect(request.referrer or url_for("main.show_top"))


@bp.route("/favorites/artworks/<int:artwork_id>/remove", methods=["POST"])
@login_required
def remove_artwork_favorite(artwork_id):
    row = ArtworkFavorite.query.filter_by(
        user_id=current_user.id, artwork_id=artwork_id
    ).first()
    if row:
        db.session.delete(row)
        db.session.commit()
        flash("作品のお気に入りを解除しました。", "info")
    return redirect(request.referrer or url_for("auth.show_account"))


@bp.route("/favorites/auctions/<int:auction_id>/add", methods=["POST"])
@login_required
def add_auction_favorite(auction_id):
    auction = db.session.get(Auction, auction_id)
    if auction is None:
        abort(404)
    exists = AuctionFavorite.query.filter_by(
        user_id=current_user.id, auction_id=auction_id
    ).first()
    if exists is None:
        db.session.add(AuctionFavorite(user_id=current_user.id, auction_id=auction_id))
        db.session.commit()
        flash("オークションをお気に入りに登録しました。", "info")
    return redirect(request.referrer or url_for("auctions.show_auction_detail", auction_id=auction_id))


@bp.route("/favorites/auctions/<int:auction_id>/remove", methods=["POST"])
@login_required
def remove_auction_favorite(auction_id):
    row = AuctionFavorite.query.filter_by(
        user_id=current_user.id, auction_id=auction_id
    ).first()
    if row:
        db.session.delete(row)
        db.session.commit()
        flash("オークションのお気に入りを解除しました。", "info")
    return redirect(request.referrer or url_for("auth.show_account"))
