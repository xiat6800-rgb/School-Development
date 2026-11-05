import io

import pytest
from PIL import Image
from werkzeug.datastructures import FileStorage

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import Artwork, Auction, User
from app.services import artwork_service, auction_service


@pytest.fixture()
def app(tmp_path):
    app = create_app(TestConfig)
    app.config["UPLOAD_FOLDER"] = str(tmp_path / "uploads")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def make_png_bytes(size=(1024, 1024), color=(255, 200, 100)):
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def make_file_storage(name="image.png", size=(1024, 1024)):
    return FileStorage(
        stream=make_png_bytes(size=size), filename=name, content_type="image/png"
    )


def register(client, username="alice", password="password123"):
    return client.post(
        "/register",
        data={
            "username": username,
            "password": password,
            "password_confirm": password,
        },
        follow_redirects=True,
    )


def login(client, username="alice", password="password123"):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


def create_user(app, username="alice", balance=10000):
    with app.app_context():
        user = User(username=username, disp_name=username)
        user.set_password("password123")
        user.point_balance = balance
        db.session.add(user)
        db.session.commit()
        return user.id


def create_saved_draft(app, user_id, title="作品A", artist=None):
    """正式保存済みの下書きを作る（サービス経由でボーナスも一括確認できる）。"""
    with app.app_context():
        user = db.session.get(User, user_id)
        artwork = Artwork(
            artist_id=user.id,
            title=title,
            status=Artwork.STATUS_DRAFT,
            duration_seconds=30,
        )
        db.session.add(artwork)
        db.session.commit()
        artwork_service.save_draft_assets(
            artwork,
            make_file_storage("composite.png"),
            [make_file_storage("layer0.png"), make_file_storage("layer1.png")],
            [
                {"name": "下", "visible": True, "opacity": 1.0},
                {"name": "上", "visible": True, "opacity": 0.8},
            ],
        )
        return artwork.id


def create_auction(app, artwork_id, user_id, start_price=100, duration_minutes=10):
    with app.app_context():
        artwork = db.session.get(Artwork, artwork_id)
        user = db.session.get(User, user_id)
        auction = auction_service.create_auction(
            artwork,
            user,
            title=artwork.title,
            description="",
            tag_ids=[],
            start_price=start_price,
            duration_minutes=duration_minutes,
        )
        return auction.id
