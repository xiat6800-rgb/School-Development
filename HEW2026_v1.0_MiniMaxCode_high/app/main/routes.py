"""ホーム画面。

ゲストは公開作品・開催中オークション・タグ検索を閲覧できる。
"""

from __future__ import annotations

from flask import render_template
from flask_login import current_user

from app.main import main_bp
from app.models.artwork import Artwork
from app.models.auction import ACTIVE, Auction
from app.models.tag import Tag


@main_bp.route("/")
def home():
    """ホーム画面を表示する。"""
    artworks = (
        Artwork.query.filter(Artwork.status.in_(("listed", "sold")))
        .order_by(Artwork.created_at.desc(), Artwork.id.desc())
        .limit(12)
        .all()
    )
    auctions = (
        Auction.query.filter(Auction.status == ACTIVE)
        .order_by(Auction.end_time.asc())
        .limit(12)
        .all()
    )
    tags = Tag.query.order_by(Tag.name.asc()).all()
    return render_template(
        "main/home.html",
        artworks=artworks,
        auctions=auctions,
        tags=tags,
    )
