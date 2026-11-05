"""アカウント画面の Blueprint。"""

from flask import Blueprint

account_bp = Blueprint("account", __name__)

from app.account import routes as _routes  # noqa: E402,F401  (登録のため読み込む)
