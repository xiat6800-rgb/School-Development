"""描画・下書き・出品設定の Blueprint。"""

from flask import Blueprint

artworks_bp = Blueprint("artworks", __name__)

from app.artworks import routes as _routes  # noqa: E402,F401  (登録のため読み込む)
