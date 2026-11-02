"""ホーム画面の Blueprint。"""

from flask import Blueprint

main_bp = Blueprint("main", __name__)

from app.main import routes as _routes  # noqa: E402,F401  (登録のため読み込む)
