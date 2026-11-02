"""公開作品のタグ検索（複数タグは AND 条件）。"""

from __future__ import annotations

from flask import render_template, request

from app.search import search_bp
from app.services import tag_service


@search_bp.route("/search/")
def search_artworks():
    """検索条件を受け付け、結果を表示する。"""
    tags = tag_service.list_tags()
    raw_ids = request.args.getlist("tag_ids")
    keyword = (request.args.get("keyword") or "").strip()

    selected_ids = []
    for raw in raw_ids:
        try:
            selected_ids.append(int(raw))
        except ValueError:
            continue

    results = tag_service.find_artworks_by_tags(selected_ids, keyword)
    if not selected_ids and keyword:
        # タグ未指定・キーワード指定のときは公開作品をタイトル・説明から絞り込む
        from app.models.artwork import Artwork
        from app.extensions import db

        pattern = f"%{keyword}%"
        results = (
            Artwork.query.filter(Artwork.status.in_(("listed", "sold")))
            .filter(
                db.or_(
                    Artwork.title.like(pattern),
                    Artwork.description.like(pattern),
                )
            )
            .order_by(Artwork.created_at.desc())
            .all()
        )

    return render_template(
        "search/index.html",
        tags=tags,
        selected_ids=selected_ids,
        keyword=keyword,
        results=results,
    )
