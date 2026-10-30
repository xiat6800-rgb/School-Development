"""pytest 共通フィクスチャ.

ポイント:
- 本番用の Config をそのまま使わず、TestConfig を継承して上書きする。
- DB は sqlite のメモリ DB（sqlite://）なので、DB ファイルが残らない。
- UPLOAD_ROOT は tmp_path に逃がす（CI 上で書ける場所を保証する）。
- DB はアプリ生成ごとに作り直すので、テスト同士が汚染し合わない。
"""

import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db as _db


@pytest.fixture()
def app(tmp_path):
    """テストごとに新品のアプリを作る。"""

    config = type(
        "CiTestConfig",
        (TestConfig,),
        {
            "SECRET_KEY": "test-only-secret",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "UPLOAD_ROOT": str(tmp_path / "uploads"),
            # イベント終了時刻を未設定にして「開催中」の状態でテストする
            "EVENT_ENDS_AT": None,
            "APP_STOPS_AT": None,
            "SEED_DEMO": False,
            "WTF_CSRF_ENABLED": False,
        },
    )

    application = create_app(config)

    with application.app_context():
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def runner(app):
    return app.test_cli_runner()


@pytest.fixture()
def make_user(app):
    """ユーザーを直接作るヘルパー（画面操作を介さず前提条件を用意する）。"""

    from app.models import User

    def _make(username="alice", password="password123"):
        user = User(username=username, disp_name=f"user_{username}")
        user.set_password(password)
        _db.session.add(user)
        _db.session.commit()
        return user

    return _make


@pytest.fixture()
def logged_in_client(client, make_user):
    """ログイン済みのクライアントを返す。"""

    make_user(username="alice", password="password123")
    client.post(
        "/auth/login",
        data={"username": "alice", "password": "password123"},
        follow_redirects=True,
    )
    return client
