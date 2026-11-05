from flask import Blueprint

bp = Blueprint("auctions", __name__)

from . import routes  # noqa: E402,F401
