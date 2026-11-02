"""商品詳細・入札・自動入札の Blueprint。"""

from flask import Blueprint

auctions_bp = Blueprint("auctions", __name__)

from app.auctions import routes as _routes  # noqa: E402,F401  (登録のため読み込む)
