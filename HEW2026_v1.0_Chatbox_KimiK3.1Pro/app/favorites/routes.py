from flask import flash, redirect, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.favorites import bp
from app.models import ArtworkFavorite, AuctionFavorite


def _back():
    return redirect(request.referrer or url_for("main.index"))


@bp.post("/artworks/<int:artwork_id>/toggle")
@login_required
def toggle_artwork_favorite(artwork_id):
    favorite = ArtworkFavorite.query.filter_by(
        user_id=current_user.id, artwork_id=artwork_id
    ).first()
    if favorite:
        db.session.delete(favorite)
        flash("作品のお気に入りを解除しました。", "success")
    else:
        db.session.add(ArtworkFavorite(user_id=current_user.id, artwork_id=artwork_id))
        flash("作品をお気に入り登録しました。", "success")
    db.session.commit()
    return _back()


@bp.post("/auctions/<int:auction_id>/toggle")
@login_required
def toggle_auction_favorite(auction_id):
    favorite = AuctionFavorite.query.filter_by(
        user_id=current_user.id, auction_id=auction_id
    ).first()
    if favorite:
        db.session.delete(favorite)
        flash("オークションのお気に入りを解除しました。", "success")
    else:
        db.session.add(AuctionFavorite(user_id=current_user.id, auction_id=auction_id))
        flash("オークションをお気に入り登録しました。", "success")
    db.session.commit()
    return _back()
