"""タグの検索と作品への関連付け。

複数タグを指定した場合は AND 条件（選択したすべてのタグを持つ作品）を返す。
"""

from __future__ import annotations

from app.extensions import db
from app.models.artwork import DRAFT, Artwork
from app.models.tag import ArtworkTag, Tag
from app.services.errors import ValidationError

# 公開状態（draft 以外は誰でも閲覧できる）
PUBLIC_STATUSES = ("listed", "sold")


def list_tags() -> list[Tag]:
    """選択可能な既存タグを名前順で取得する。"""
    return Tag.query.order_by(Tag.name.asc()).all()


def find_artworks_by_tags(tag_ids: list[int], keyword: str | None = None) -> list:
    """指定したすべてのタグを持つ公開作品を取得する（AND 条件）。"""
    ids = {int(tag_id) for tag_id in tag_ids if tag_id is not None}
    if not ids:
        return []

    query = (
        db.session.query(Artwork)
        .join(ArtworkTag, ArtworkTag.artwork_id == Artwork.id)
        .filter(ArtworkTag.tag_id.in_(ids))
        .filter(Artwork.status.in_(PUBLIC_STATUSES))
        .group_by(Artwork.id)
        .having(db.func.count(db.distinct(ArtworkTag.tag_id)) == len(ids))
    )
    if keyword:
        pattern = f"%{keyword.strip()}%"
        query = query.filter(
            db.or_(
                Artwork.title.like(pattern),
                Artwork.description.like(pattern),
            )
        )
    return query.order_by(Artwork.created_at.desc()).all()


def set_artwork_tags(artwork, tag_ids: list[int]) -> None:
    """既存タグだけを作品に関連付け、重複付与を防ぐ。"""
    if not tag_ids:
        return
    tags = Tag.query.filter(Tag.id.in_([int(t) for t in tag_ids])).all()
    if len(tags) != len({int(t) for t in tag_ids}):
        raise ValidationError("存在しないタグが含まれています。")
    current = {link.tag_id for link in artwork.tag_links}
    for tag in tags:
        if tag.id not in current:
            artwork.tag_links.append(ArtworkTag(tag_id=tag.id))


def remove_artwork_tags(artwork) -> None:
    """作品に付与されたタグの関連付けを解除する。"""
    for link in list(artwork.tag_links):
        artwork.tag_links.remove(link)
    db.session.flush()


def is_draft(artwork) -> bool:
    """作品を下書きとして扱うかどうかを返す。"""
    return artwork.status == DRAFT
