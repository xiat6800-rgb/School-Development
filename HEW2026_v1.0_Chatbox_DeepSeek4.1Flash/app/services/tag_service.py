"""タグの取得・AND 検索・作品への関連付け。"""

from ..constants import (
    ARTWORK_STATUS_LISTED,
    ARTWORK_STATUS_SOLD,
    ARTWORK_VISIBILITY_PUBLIC,
)
from ..extensions import db
from ..models import Artwork, Tag, artwork_tags


def list_tags():
    """選択可能な既存タグを取得する。"""
    return db.session.scalars(db.select(Tag).order_by(Tag.name)).all()


def get_tags_by_ids(tag_ids):
    """ID 指定でタグを取得する。存在しない ID は無視する。"""
    ids = {int(tag_id) for tag_id in tag_ids or [] if str(tag_id).isdigit()}
    if not ids:
        return []
    return db.session.scalars(db.select(Tag).where(Tag.id.in_(ids))).all()


def set_artwork_tags(artwork, tag_ids):
    """既存タグだけを作品へ関連付ける。同じタグの重複付与はしない。"""
    artwork.tags = get_tags_by_ids(tag_ids)
    db.session.flush()
    return artwork.tags


def find_artworks_by_tags(tag_ids, limit=60):
    """指定したすべてのタグを持つ公開作品を取得する（AND 条件）。"""
    ids = sorted({int(tag_id) for tag_id in tag_ids or [] if str(tag_id).isdigit()})
    if not ids:
        return []
    statement = (
        db.select(Artwork)
        .join(artwork_tags, Artwork.id == artwork_tags.c.artwork_id)
        .where(
            artwork_tags.c.tag_id.in_(ids),
            Artwork.status.in_((ARTWORK_STATUS_LISTED, ARTWORK_STATUS_SOLD)),
            Artwork.visibility == ARTWORK_VISIBILITY_PUBLIC,
        )
        .group_by(Artwork.id)
        .having(db.func.count(db.func.distinct(artwork_tags.c.tag_id)) == len(ids))
        .order_by(Artwork.created_at.desc())
        .limit(limit)
    )
    return db.session.scalars(statement).all()
