"""テスト用の共通フィクスチャ。

テストは既定で専用の MySQL テストデータベースを使う
（``TEST_DATABASE_URL`` で上書きできる）。開発用 DB とは分離している。
"""

from __future__ import annotations

import base64
from datetime import timedelta

import pytest

from app import create_app
from app.extensions import db
from app.models.artwork import Artwork
from app.models.auction import Auction
from app.models.user import User
from app.services.image_service import create_solid_png
from app.utils import utcnow


@pytest.fixture()
def app(tmp_path):
    """テスト用の Flask アプリ。"""
    application = create_app("testing")
    application.config["UPLOAD_FOLDER"] = str(tmp_path / "uploads")
    application.config["WTF_CSRF_ENABLED"] = False
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    """テストクライアント。"""
    return app.test_client()


@pytest.fixture()
def runner(app):
    """Flask CLI のテストランナー。"""
    return app.test_cli_runner()


@pytest.fixture()
def make_user(app):
    """ユーザーを作成するヘルパー。"""

    def _make(username: str = "alice", password: str = "password123", points: int = 1000):
        user = User(username=username, disp_name=username, point_balance=points)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user

    return _make


@pytest.fixture()
def login(client):
    """ログイン状態を作るヘルパー。"""

    def _login(username: str, password: str = "password123"):
        return client.post(
            "/auth/login",
            data={"username": username, "password": password},
            follow_redirects=True,
        )

    return _login


@pytest.fixture()
def png_data_url():
    """正当な PNG の data URL を返す。"""
    raw = create_solid_png(64, 64, (120, 160, 200))
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


@pytest.fixture()
def make_artwork(app, make_user):
    """保存済み画像の作品を作成するヘルパー。"""
    from app.services.image_service import save_png
    from app.services.layer_service import save_layer_archive

    def _make(artist, title: str = "テスト作品", status: str = "draft"):
        artwork = Artwork(
            artist_id=artist.id,
            title=title,
            description="テスト用の説明",
            status=status,
        )
        db.session.add(artwork)
        db.session.flush()

        png = create_solid_png(64, 64, (120, 160, 200))
        artwork.image_path = save_png(png)
        artwork.layer_archive_path = save_layer_archive(
            [{"name": "レイヤー1", "visible": True, "opacity": 1.0, "data": png}]
        )
        artwork.save_completed_at = utcnow()
        db.session.commit()
        return artwork

    return _make


@pytest.fixture()
def make_auction(app, make_artwork, make_user):
    """開催中のオークションを作るヘルパー。"""
    from app.models.artwork import LISTED

    def _make(seller, start_price: int = 100, minutes: int = 10, status: str = "active"):
        artwork = make_artwork(seller, status=LISTED)
        now = utcnow()
        auction = Auction(
            artwork_id=artwork.id,
            start_price=start_price,
            current_price=start_price,
            status=status,
            start_time=now,
            end_time=now + timedelta(minutes=minutes),
        )
        db.session.add(auction)
        db.session.commit()
        return auction

    return _make
