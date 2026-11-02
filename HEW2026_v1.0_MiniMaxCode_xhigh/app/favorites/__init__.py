"""お気に入りの Blueprint。"""

from flask import Blueprint

favorites_bp = Blueprint("favorites", __name__)

from app.favorites import routes as _routes  # noqa: E402,F401  (登録のため読み込む)
