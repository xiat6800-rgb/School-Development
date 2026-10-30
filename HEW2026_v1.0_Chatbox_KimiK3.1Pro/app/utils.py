from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import abort
from flask_login import current_user


JST = timezone(timedelta(hours=9))


def utcnow():
    """DBには naive UTC、画面にはJSTを使う。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_jst(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(JST)


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped
