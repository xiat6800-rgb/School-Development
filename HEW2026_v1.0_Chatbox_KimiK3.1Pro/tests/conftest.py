from datetime import timedelta

import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import Artwork, Tag, User
from app.utils import utcnow


@pytest.fixture
def app(tmp_path):
    class Config(TestConfig):
        UPLOAD_FOLDER = str(tmp_path / "uploads")
        SERVER_NAME = "localhost"

    app = create_app(Config)
    with app.app_context():
        db.create_all()
        for name in ("風景", "カラー"):
            db.session.add(Tag(name=name))
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def create_user(username, balance=1000, role="user"):
    user = User(username=username, display_name=username, role=role, point_balance=balance)
    user.set_password("test-password")
    db.session.add(user)
    db.session.flush()
    return user


def create_saved_artwork(artist, title="テスト作品"):
    now = utcnow()
    artwork = Artwork(
        artist=artist, title=title, description="テスト用の正式保存済み作品",
        image_path=f"test/{artist.id}-{title}.png",
        archive_path=f"test/{artist.id}-{title}.zip",
        status="draft", is_public=False,
        drawing_started_at=now - timedelta(minutes=5),
        drawing_ends_at=now - timedelta(minutes=1),
        finished_at=now - timedelta(minutes=2), saved_at=now - timedelta(minutes=2),
        duration_seconds=300,
    )
    db.session.add(artwork)
    db.session.flush()
    return artwork
