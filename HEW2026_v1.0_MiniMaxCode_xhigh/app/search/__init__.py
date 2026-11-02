"""タグ検索の Blueprint。"""

from flask import Blueprint

search_bp = Blueprint("search", __name__)

from app.search import routes as _routes  # noqa: E402,F401  (登録のため読み込む)
