"""作品・オークションのお気に入り登録と解除。

作品用（artwork_bookmarks）とオークション用（bookmarks）は別テーブルで管理する。
"""

from __future__ import annotations

from flask import flash, redirect, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.favorites import favorites_bp
from app.models.favorite import ArtworkFavorite, AuctionFavorite
from app.services.errors import NotFoundError


@favorites_bp.route("/favorites/artworks/<int:artwork_id>/toggle", methods=["POST"])
@login_required
def toggle_artwork_favorite(artwork_id: int):
    """作品のお気に入りを登録・解除する。"""
    from app.models.artwork import Artwork

    artwork = Artwork.query.get(artwork_id)
    if artwork is None:
        raise NotFoundError("作品が見つかりません。")
    if not artwork.is_public:
        flash("公開中の作品だけお気に入りに登録できます。", "error")
        return redirect(url_for("main.home"))

    existing = ArtworkFavorite.query.filter_by(
        user_id=current_user.id, artwork_id=artwork_id
    ).first()
    if existing is not None:
        db.session.delete(existing)
        db.session.commit()
        flash("作品のお気に入りから解除しました。", "success")
    else:
        db.session.add(
            ArtworkFavorite(user_id=current_user.id, artwork_id=artwork_id)
        )
        db.session.commit()
        flash("作品をお気に入りに登録しました。", "success")

    return redirect(_back_to(request.form.get("back_to")))


@favorites_bp.route("/favorites/auctions/<int:auction_id>/toggle", methods=["POST"])
@login_required
def toggle_auction_favorite(auction_id: int):
    """オークションのお気に入りを登録・解除する。"""
    from app.models.auction import Auction

    auction = Auction.query.get(auction_id)
    if auction is None:
        raise NotFoundError("オークションが見つかりません。")

    existing = AuctionFavorite.query.filter_by(
        user_id=current_user.id, auction_id=auction_id
    ).first()
    if existing is not None:
        db.session.delete(existing)
        db.session.commit()
        flash("オークションのお気に入りから解除しました。", "success")
    else:
        db.session.add(AuctionFavorite(user_id=current_user.id, auction_id=auction_id))
        db.session.commit()
        flash("オークションをお気に入りに登録しました。", "success")

    return redirect(_back_to(request.form.get("back_to")))


def _back_to(target: str | None) -> str:
    """戻り先。外部サイトへの遷移を防ぐ。"""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("main.home")
