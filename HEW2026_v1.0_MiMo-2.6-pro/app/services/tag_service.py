"""タグマスタと作品タグの関連付け。"""

from app.extensions import db
from app.models import Artwork, ArtworkTag, Tag


def list_tags():
    return Tag.query.order_by(Tag.name).all()


def get_tags_by_ids(tag_ids):
    if not tag_ids:
        return []
    return Tag.query.filter(Tag.id.in_(tag_ids)).all()


def set_artwork_tags(artwork, tag_ids):
    """既存タグだけを作品に関連付ける。同一タグの重複付与は防ぐ。"""
    tags = get_tags_by_ids(tag_ids)
    valid_ids = {tag.id for tag in tags}
    ArtworkTag.query.filter_by(artwork_id=artwork.id).delete()
    seen = set()
    for tag_id in valid_ids:
        if tag_id in seen:
            continue
        seen.add(tag_id)
        db.session.add(ArtworkTag(artwork_id=artwork.id, tag_id=tag_id))
    return tags


def find_artworks_by_tags(tag_ids, status=Artwork.STATUS_LISTED):
    """指定したすべてのタグを持つ公開作品を取得する（AND条件）。"""
    if not tag_ids:
        return []
    tag_ids = list(set(tag_ids))
    count = len(tag_ids)
    query = (
        Artwork.query.join(ArtworkTag, ArtworkTag.artwork_id == Artwork.id)
        .filter(Artwork.status.in_((status, Artwork.STATUS_SOLD)))
        .filter(ArtworkTag.tag_id.in_(tag_ids))
        .group_by(Artwork.id)
        .having(db.func.count(db.distinct(ArtworkTag.tag_id)) == count)
        .order_by(Artwork.created_at.desc())
    )
    return query.all()


def list_public_artworks(statuses=None):
    if statuses is None:
        statuses = (Artwork.STATUS_LISTED, Artwork.STATUS_SOLD)
    return (
        Artwork.query.filter(Artwork.status.in_(statuses))
        .order_by(Artwork.created_at.desc())
        .all()
    )


def list_artwork_tag_names(artwork):
    links = ArtworkTag.query.filter_by(artwork_id=artwork.id).all()
    return [link.tag.name for link in links if link.tag]
