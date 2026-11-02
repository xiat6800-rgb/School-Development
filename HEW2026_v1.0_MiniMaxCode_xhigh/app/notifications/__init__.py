"""通知の Blueprint。"""

from flask import Blueprint

notifications_bp = Blueprint("notifications", __name__)

from app.notifications import routes as _routes  # noqa: E402,F401  (登録のため読み込む)
