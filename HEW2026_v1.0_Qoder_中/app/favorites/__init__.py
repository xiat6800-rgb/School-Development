from flask import Blueprint

bp = Blueprint("favorites", __name__)

from . import routes  # noqa: E402,F401
