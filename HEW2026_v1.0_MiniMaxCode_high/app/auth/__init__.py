"""認証・アカウント復旧の Blueprint。"""

from flask import Blueprint

auth_bp = Blueprint("auth", __name__)

from app.auth import routes as _routes  # noqa: E402,F401  (登録のため読み込む)
