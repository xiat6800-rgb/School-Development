import os
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    # 相対パスの SQLite は instance/ 配下に解決される
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///hew_dev.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.environ.get(
        "UPLOAD_FOLDER",
        os.path.join(os.path.dirname(__file__), "static", "uploads", "artworks"),
    )
    MAX_PNG_BYTES = int(os.environ.get("MAX_PNG_MIB", 5)) * 1024 * 1024
    MAX_LAYER_BYTES = int(os.environ.get("MAX_LAYER_MIB", 5)) * 1024 * 1024
    MAX_LAYERS_TOTAL_BYTES = (
        int(os.environ.get("MAX_LAYERS_TOTAL_MIB", 50)) * 1024 * 1024
    )
    MAX_CONTENT_LENGTH = 64 * 1024 * 1024

    # 描画の猶予（秒）：固定後は保存だけ再試行できる
    SAVE_GRACE_SECONDS = 60
    CANVAS_SIZE = 1024
    MAX_LAYERS = 10
    MAX_UNDO = 50

    # ボーナス（2026/10/26 合意の仮データ）
    BONUS_REGISTER = 1000
    BONUS_FIRST_LISTING = 300
    BONUS_DRAWING_SAVE = 100

    # 1日開催のイベント終了日時（UTC）。None なら無期限。
    EVENT_END_AT = None

    WTF_CSRF_ENABLED = True

    @classmethod
    def init_from_env(cls):
        raw = os.environ.get("EVENT_END_AT")
        if raw:
            parsed = datetime.fromisoformat(raw)
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            cls.EVENT_END_AT = parsed


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SECRET_KEY = "test-secret"
    EVENT_END_AT = None
