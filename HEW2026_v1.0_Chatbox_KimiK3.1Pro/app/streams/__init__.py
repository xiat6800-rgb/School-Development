from flask import Blueprint
bp = Blueprint("streams", __name__, url_prefix="/streams")
from app.streams import routes  # noqa: E402,F401
