"""ポイント関連の補助画面の Blueprint。"""

from flask import Blueprint

points_bp = Blueprint("points", __name__)

from app.points import routes as _routes  # noqa: E402,F401  (登録のため読み込む)
