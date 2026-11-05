"""タグサービス。初期タグ・AND 検索・作品へのタグ付けを提供する。"""
from ..extensions import db
from ..models.artwork import Artwork
from ..models.tag import Tag

DEFAULT_TAGS = (
    "風景", "人物", "動物", "アニメ", "抽象",
    "モノクロ", "カラー", "デジタル", "水彩風", "その他",
)


def list_tags():
    """選択可能な既存タグを取得する。"""
    return Tag.query.order_by(Tag.name).all()


def find_artworks_by_tags(tag_ids):
    """指定したすべてのタグを持つ公開作品を取得する（AND 条件）。"""
    query = Artwork.query.filter(Artwork.status.in_(("listed", "sold", "cancelled")))
    if tag_ids:
        query = (
            query.join(Artwork.tags)
            .filter(Tag.id.in_(tag_ids))
            .group_by(Artwork.id)
            .having(db.func.count(db.distinct(Tag.id)) == len(set(tag_ids)))
        )
    return query.order_by(Artwork.created_at.desc()).all()


def set_artwork_tags(artwork, tag_ids):
    """既存タグだけを作品に関連付け、重複を防止する。"""
    unique_ids = list(dict.fromkeys(tag_ids))
    tags = Tag.query.filter(Tag.id.in_(unique_ids)).all() if unique_ids else []
    artwork.tags = tags
    return tags


def seed_default_tags():
    """初期タグを準備する（管理画面の代替。開発用コマンドから呼ぶ）。"""
    created = 0
    for name in DEFAULT_TAGS:
        if not Tag.query.filter_by(name=name).first():
            db.session.add(Tag(name=name))
            created += 1
    db.session.commit()
    return created
