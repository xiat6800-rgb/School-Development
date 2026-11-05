"""タグ検索のルート。複数タグは AND 条件。"""
from flask import render_template, request

from ..services import tag_service
from . import bp


@bp.route("/search")
def search_artworks():
    """公開作品の検索条件を受け付け、結果を表示する。ゲストも利用可能。"""
    raw_ids = request.args.getlist("tag_ids")
    tag_ids = [int(v) for v in raw_ids if str(v).isdigit()]
    artworks = tag_service.find_artworks_by_tags(tag_ids)
    return render_template(
        "search/results.html",
        tags=tag_service.list_tags(),
        selected_ids=set(tag_ids),
        artworks=artworks,
        searched=bool(raw_ids),
    )
