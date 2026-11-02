"""設定の既定値が MySQL であることを確かめる。"""

from app.config import (
    DEFAULT_DATABASE_URL,
    DEFAULT_TEST_DATABASE_URL,
    Config,
    TestingConfig,
)


def test_default_urls_point_to_mysql():
    assert DEFAULT_DATABASE_URL.startswith("mysql+pymysql://")
    assert "hew_xhigh" in DEFAULT_DATABASE_URL
    assert DEFAULT_TEST_DATABASE_URL.startswith("mysql+pymysql://")
    assert "hew_xhigh_test" in DEFAULT_TEST_DATABASE_URL


def test_effective_uris_are_mysql():
    assert Config.SQLALCHEMY_DATABASE_URI.startswith("mysql+pymysql://")
    assert TestingConfig.SQLALCHEMY_DATABASE_URI.startswith("mysql+pymysql://")


def test_dev_and_test_databases_are_separated():
    dev = Config.SQLALCHEMY_DATABASE_URI
    test = TestingConfig.SQLALCHEMY_DATABASE_URI
    assert dev != test
    assert "hew_xhigh_test" not in dev
