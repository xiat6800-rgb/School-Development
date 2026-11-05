from flask import Blueprint

bp = Blueprint("notifications", __name__)

from . import routes  # noqa: E402,F401
