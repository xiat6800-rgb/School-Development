from flask import Blueprint, render_template, request

from app.services import tag_service

bp = Blueprint("search", __name__)


@bp.route("/search", methods=["GET"])
def search_artworks():
    tag_ids = request.args.getlist("tag_ids", type=int)
    tags = tag_service.list_tags()
    if tag_ids:
        artworks = tag_service.find_artworks_by_tags(tag_ids)
    else:
        artworks = tag_service.list_public_artworks()
    return render_template(
        "search/results.html",
        artworks=artworks,
        tags=tags,
        selected_tag_ids=tag_ids,
    )
