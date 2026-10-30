"""作品・競売のお気に入り登録と解除。"""

from flask import Blueprint, abort, flash, redirect, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Artwork, Auction
from ..services import favorite_service

bp = Blueprint("favorites", __name__, url_prefix="/favorites")


def _redirect_back(default_endpoint, **values):
    """安全な戻り先へリダイレクトする（外部 URL は使わない）。"""
    next_url = request.form.get("next") or ""
    if next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect(url_for(default_endpoint, **values))


@bp.post("/artworks/<int:artwork_id>")
@login_required
def toggle_artwork_favorite(artwork_id):
    """作品のお気に入りを登録・解除する。"""
    artwork = db.session.get(Artwork, artwork_id)
    if artwork is None or not artwork.is_visible_to(current_user):
        abort(404)

    action = request.form.get("action")
    favorited = favorite_service.is_artwork_favorited(
        current_user.id, artwork.id
    )
    if action == "remove" or (action is None and favorited):
        favorite_service.remove_artwork_favorite(current_user.id, artwork.id)
        flash("作品のお気に入りを解除しました。", "success")
    else:
        favorite_service.add_artwork_favorite(current_user.id, artwork.id)
        flash("作品をお気に入りに登録しました。", "success")
    return _redirect_back("main.index")


@bp.post("/auctions/<int:auction_id>")
@login_required
def toggle_auction_favorite(auction_id):
    """競売のお気に入りを登録・解除する。"""
    auction = db.session.get(Auction, auction_id)
    if auction is None:
        abort(404)

    action = request.form.get("action")
    favorited = favorite_service.is_auction_favorited(
        current_user.id, auction.id
    )
    if action == "remove" or (action is None and favorited):
        favorite_service.remove_auction_favorite(current_user.id, auction.id)
        flash("競売のお気に入りを解除しました。", "success")
    else:
        favorite_service.add_auction_favorite(current_user.id, auction.id)
        flash("競売をお気に入りに登録しました。", "success")
    return _redirect_back(
        "auctions.show_auction_detail", auction_id=auction.id
    )
