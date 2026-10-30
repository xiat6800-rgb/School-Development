"""トップページ。"""

from flask import Blueprint, render_template

from ..services import auction_service, tag_service

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    """開催中の競売と公開作品を表示する。"""
    auctions = auction_service.list_active_auctions()
    artworks = auction_service.list_public_artworks()
    return render_template(
        "index.html",
        auctions=auctions,
        artworks=artworks,
        tags=tag_service.list_tags(),
    )


@bp.get("/healthz")
def healthz():
    return {"status": "ok"}
