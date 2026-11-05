"""環境別設定。秘密情報・接続情報は .env からのみ読み込む（要件定義書 7.3）。"""
import os
import secrets

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# テスト・本番とも秘密情報をソースに書かない。開発時のみ起動ごとに自動生成する。
if os.environ.get("SECRET_KEY"):
    _SECRET_KEY = os.environ["SECRET_KEY"]
elif os.environ.get("FLASK_ENV") == "production":
    raise RuntimeError("SECRET_KEY が未設定です。.env に設定してください。")
else:
    _SECRET_KEY = secrets.token_hex(32)


def _env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = _SECRET_KEY

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "mysql+pymysql://root:@127.0.0.1:3306/hew?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = _env_bool("SQL_ECHO")
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # POST 全体の CSRF と上限サイズ
    WTF_CSRF_TIME_LIMIT = None
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024

    # 画像保存（静的ディレクトリの外に置き、権限チェック付きルートで配信する）
    UPLOAD_FOLDER = os.environ.get(
        "UPLOAD_FOLDER", os.path.join("app", "uploads", "artworks")
    )
    MAX_IMAGE_BYTES = _env_int("MAX_IMAGE_BYTES", 2 * 1024 * 1024)
    MAX_IMAGE_WIDTH = _env_int("MAX_IMAGE_WIDTH", 2048)
    MAX_IMAGE_HEIGHT = _env_int("MAX_IMAGE_HEIGHT", 2048)
    CANVAS_WIDTH = _env_int("CANVAS_WIDTH", 800)
    CANVAS_HEIGHT = _env_int("CANVAS_HEIGHT", 600)

    # 未決事項の既定値（要件定義書 9章）
    BID_INCREMENT = _env_int("BID_INCREMENT", 100)
    BONUS_SIGNUP_POINTS = _env_int("BONUS_SIGNUP_POINTS", 1000)
    BONUS_FIRST_LISTING_POINTS = _env_int("BONUS_FIRST_LISTING_POINTS", 500)
    BONUS_DRAW_POINTS = _env_int("BONUS_DRAW_POINTS", 100)
    BONUS_DRAW_MAX_TIMES = _env_int("BONUS_DRAW_MAX_TIMES", 10)

    # 通知メール（未設定時は配信記録を pending のまま残す）
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = _env_int("MAIL_PORT", 587)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_USE_TLS = _env_bool("MAIL_USE_TLS", True)
    MAIL_DEFAULT_SENDER = os.environ.get(
        "MAIL_DEFAULT_SENDER", "no-reply@hew2026.local"
    )

    @staticmethod
    def upload_path():
        path = os.environ.get("UPLOAD_FOLDER", os.path.join("app", "uploads", "artworks"))
        if not os.path.isabs(path):
            path = os.path.join(BASE_DIR, path)
        return path


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_DATABASE_URI = os.environ.get("TEST_DATABASE_URL") or "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}


def get_config():
    if os.environ.get("FLASK_ENV") == "testing":
        return TestingConfig
    return Config
