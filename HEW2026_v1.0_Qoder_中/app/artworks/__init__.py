from flask import Blueprint

bp = Blueprint("artworks", __name__)

from . import routes  # noqa: E402,F401
