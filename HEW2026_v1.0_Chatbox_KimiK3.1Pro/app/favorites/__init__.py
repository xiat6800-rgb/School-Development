from flask import Blueprint
bp = Blueprint("favorites", __name__, url_prefix="/favorites")
from app.favorites import routes  # noqa: E402,F401
