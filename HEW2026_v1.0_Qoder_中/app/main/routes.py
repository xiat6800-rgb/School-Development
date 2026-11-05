"""トップページ。公開作品と開催中のオークションを表示する。"""
from flask import render_template

from ..extensions import db
from ..models.artwork import Artwork
from ..models.auction import Auction
from . import bp


@bp.route("/")
def show_top():
    artworks = (
        Artwork.query.filter(Artwork.status.in_(("listed", "sold")))
        .order_by(Artwork.created_at.desc())
        .limit(48)
        .all()
    )
    auctions = (
        Auction.query.filter_by(status="active")
        .order_by(Auction.end_time.asc())
        .limit(48)
        .all()
    )
    return render_template("top.html", artworks=artworks, auctions=auctions)
