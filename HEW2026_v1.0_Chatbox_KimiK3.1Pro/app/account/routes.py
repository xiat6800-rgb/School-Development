from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.account import bp
from app.extensions import db
from app.models import (
    Artwork, ArtworkFavorite, AuctionFavorite, AutoBid, WalletTransaction,
)
from app.services.common import BusinessError


@bp.get("")
@login_required
def show_account():
    artworks = Artwork.query.filter_by(artist_id=current_user.id).order_by(
        Artwork.id.desc()
    ).all()
    artwork_favorites = ArtworkFavorite.query.filter_by(
        user_id=current_user.id
    ).order_by(ArtworkFavorite.id.desc()).all()
    auction_favorites = AuctionFavorite.query.filter_by(
        user_id=current_user.id
    ).order_by(AuctionFavorite.id.desc()).all()
    auto_bids = AutoBid.query.filter_by(user_id=current_user.id).order_by(
        AutoBid.id.desc()
    ).all()
    transactions = WalletTransaction.query.filter_by(
        user_id=current_user.id
    ).order_by(WalletTransaction.id.desc()).limit(80).all()
    return render_template(
        "account/show.html", artworks=artworks,
        artwork_favorites=artwork_favorites, auction_favorites=auction_favorites,
        auto_bids=auto_bids, transactions=transactions,
    )


@bp.post("/display-name")
@login_required
def update_display_name():
    name = request.form.get("display_name", "").strip()
    if not 1 <= len(name) <= 50:
        raise BusinessError("表示名は1〜50文字で入力してください。")
    current_user.display_name = name
    db.session.commit()
    flash("表示名を更新しました。", "success")
    return redirect(url_for("account.show_account"))
