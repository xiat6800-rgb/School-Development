from flask import Blueprint
bp = Blueprint("artworks", __name__, url_prefix="/artworks")
from app.artworks import routes  # noqa: E402,F401
