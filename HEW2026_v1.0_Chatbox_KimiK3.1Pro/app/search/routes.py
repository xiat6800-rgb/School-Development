from flask import render_template, request
from sqlalchemy import func

from app.models import Artwork, Tag, artwork_tags
from app.search import bp


@bp.get("")
def search_artworks():
    keyword = request.args.get("q", "").strip()
    try:
        selected_ids = sorted({int(v) for v in request.args.getlist("tags")})
    except ValueError:
        selected_ids = []
    query = Artwork.query.filter(
        Artwork.is_public.is_(True), Artwork.status != "draft"
    )
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(Artwork.title.ilike(like) | Artwork.description.ilike(like))
    if selected_ids:
        query = query.join(artwork_tags).filter(
            artwork_tags.c.tag_id.in_(selected_ids)
        ).group_by(Artwork.id).having(
            func.count(func.distinct(artwork_tags.c.tag_id)) == len(selected_ids)
        )
    artworks = query.order_by(Artwork.id.desc()).all()
    tags = Tag.query.order_by(Tag.name).all()
    return render_template(
        "search/results.html", artworks=artworks, tags=tags,
        selected_ids=selected_ids, keyword=keyword,
    )
