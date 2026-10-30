import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
JST = timezone(timedelta(hours=9))


def _event_time(name, default):
    value = os.environ.get(name)
    if not value:
        return default
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=JST)
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///hew_v1.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    MAX_CONTENT_LENGTH = 60 * 1024 * 1024
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER") or str(
        BASE_DIR / "instance" / "uploads"
    )
    EVENT_STARTS_AT = _event_time(
        "EVENT_STARTS_AT", datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    )
    EVENT_ENDS_AT = _event_time(
        "EVENT_ENDS_AT", datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=12)
    )
    APP_ENDS_AT = _event_time(
        "APP_ENDS_AT", datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=14)
    )
    BONUS_REGISTER = int(os.environ.get("BONUS_REGISTER", "1000"))
    BONUS_FIRST_LISTING = int(os.environ.get("BONUS_FIRST_LISTING", "300"))
    BONUS_DAILY_DRAWING = int(os.environ.get("BONUS_DAILY_DRAWING", "100"))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    EVENT_STARTS_AT = datetime(2026, 1, 1, 0, 0)
    EVENT_ENDS_AT = datetime(2030, 1, 1, 0, 0)
    APP_ENDS_AT = datetime(2030, 1, 1, 2, 0)
