"""初期タグの登録（管理画面は Ver0.5 対象外のため CLI で準備する）。"""
from app.extensions import db
from app.models import Tag

INITIAL_TAGS = [
    "動物",
    "風景",
    "人物",
    "抽象",
    "幻想",
    "静物",
    "モノクロ",
    "カラー",
]


def seed_initial_tags():
    created = 0
    for name in INITIAL_TAGS:
        exists = db.session.query(Tag).filter(Tag.name == name).first()
        if not exists:
            db.session.add(Tag(name=name))
            created += 1
    db.session.commit()
    return created
