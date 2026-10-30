from flask import Blueprint
bp = Blueprint("points", __name__, url_prefix="/points")
from app.points import routes  # noqa: E402,F401
