"""タグの AND 検索（要件定義書 5.8）。"""
from flask import Blueprint, render_template, request
from sqlalchemy import func, select

from app.extensions import db
from app.models import Artwork, Tag, artwork_tags

bp = Blueprint("search", __name__, url_prefix="/search")


@bp.route("/")
def index():
    keyword = (request.args.get("q") or "").strip()[:100]
    raw_tag_ids = request.args.getlist("tags")
    tag_ids = sorted({int(value) for value in raw_tag_ids if value.isdigit()})

    query = select(Artwork).where(Artwork.status.in_(["listed", "sold"]))
    if tag_ids:
        # 選択したすべてのタグを持つ作品だけを返す（AND 検索）
        matching = (
            select(artwork_tags.c.artwork_id)
            .where(artwork_tags.c.tag_id.in_(tag_ids))
            .group_by(artwork_tags.c.artwork_id)
            .having(func.count(func.distinct(artwork_tags.c.tag_id)) == len(tag_ids))
        )
        query = query.where(Artwork.id.in_(matching))
    if keyword:
        query = query.where(
            Artwork.title.contains(keyword, autoescape=True)
            | Artwork.description.contains(keyword, autoescape=True)
        )

    artworks = (
        db.session.execute(query.order_by(Artwork.created_at.desc()).limit(60))
        .scalars()
        .all()
    )
    tags = db.session.execute(select(Tag).order_by(Tag.id.asc())).scalars().all()
    selected = [tag for tag in tags if tag.id in tag_ids]

    return render_template(
        "search/index.html",
        artworks=artworks,
        tags=tags,
        selected=selected,
        selected_ids=tag_ids,
        keyword=keyword,
    )
