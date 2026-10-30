from flask import Blueprint
bp = Blueprint("auctions", __name__, url_prefix="/auctions")
from app.auctions import routes  # noqa: E402,F401
