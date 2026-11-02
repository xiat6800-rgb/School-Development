"""設定の既定値が MySQL であることを確かめる。"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

import app.config
from app.config import (
    DEFAULT_DATABASE_URL,
    DEFAULT_TEST_DATABASE_URL,
    Config,
    TestingConfig,
)


def _db_name(url: str) -> str | None:
    """接続 URL からデータベース名を取り出す。"""
    return make_url(url).database


@pytest.fixture()
def config_without_env(monkeypatch):
    """DATABASE_URL 等が無い状態で読み直した ``app.config``。

    ``.env`` があると reload 時に読み直されて環境変数が復活して
    しまうため、読み込みの間だけ「``.env`` が無い」状態にする。
    """
    env_path = Path(app.config.__file__).resolve().parent.parent / ".env"
    real_exists = Path.exists

    def _exists(self):
        if self == env_path:
            return False
        return real_exists(self)

    monkeypatch.setattr(Path, "exists", _exists)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    importlib.reload(app.config)
    try:
        yield app.config
    finally:
        # 環境変数を戻してから読み直し、モジュールを元の状態に戻す。
        monkeypatch.undo()
        importlib.reload(app.config)


def test_default_urls_point_to_mysql():
    assert DEFAULT_DATABASE_URL.startswith("mysql+pymysql://")
    assert _db_name(DEFAULT_DATABASE_URL) == "hew_xhigh"
    assert DEFAULT_TEST_DATABASE_URL.startswith("mysql+pymysql://")
    assert _db_name(DEFAULT_TEST_DATABASE_URL) == "hew_xhigh_test"


def test_effective_uris_are_mysql():
    assert _db_name(Config.SQLALCHEMY_DATABASE_URI) == "hew_xhigh"
    assert _db_name(TestingConfig.SQLALCHEMY_DATABASE_URI) == "hew_xhigh_test"


def test_dev_and_test_databases_are_separated():
    dev = Config.SQLALCHEMY_DATABASE_URI
    test = TestingConfig.SQLALCHEMY_DATABASE_URI
    assert dev != test
    assert _db_name(dev) == "hew_xhigh"
    assert _db_name(test) == "hew_xhigh_test"


def test_code_defaults_are_mysql_without_env(config_without_env):
    """``.env`` が無くても、コード既定値は MySQL になる。"""
    config = config_without_env
    assert config.Config.SQLALCHEMY_DATABASE_URI == (
        config.DEFAULT_DATABASE_URL
    )
    assert config.TestingConfig.SQLALCHEMY_DATABASE_URI == (
        config.DEFAULT_TEST_DATABASE_URL
    )
    assert _db_name(config.Config.SQLALCHEMY_DATABASE_URI) == "hew_xhigh"
    assert (
        _db_name(config.TestingConfig.SQLALCHEMY_DATABASE_URI)
        == "hew_xhigh_test"
    )


def test_admin_adjust_max_points_follows_env(monkeypatch):
    """調整上限は環境変数で決められる。"""
    monkeypatch.setenv("ADMIN_ADJUST_MAX_POINTS", "250")
    importlib.reload(app.config)
    try:
        assert app.config.Config.ADMIN_ADJUST_MAX_POINTS == 250
    finally:
        monkeypatch.undo()
        importlib.reload(app.config)
