"""タグ AND 検索。"""

from flask import Blueprint, render_template, request

from ..services import auction_service, tag_service

bp = Blueprint("search", __name__, url_prefix="/search")


@bp.get("/")
def search_artworks():
    """選択したすべてのタグを持つ公開作品を返す（AND 条件）。"""
    selected_ids = [
        int(value) for value in request.args.getlist("tag") if value.isdigit()
    ]
    if selected_ids:
        artworks = tag_service.find_artworks_by_tags(selected_ids)
    else:
        artworks = auction_service.list_public_artworks(limit=60)

    return render_template(
        "search/index.html",
        tags=tag_service.list_tags(),
        selected_ids=selected_ids,
        artworks=artworks,
    )
