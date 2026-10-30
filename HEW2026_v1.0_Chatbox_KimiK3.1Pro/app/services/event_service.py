from flask import current_app

from app.services.common import BusinessError
from app.utils import utcnow


def validate_event_operation(operation="create", now=None):
    now = now or utcnow()
    if now < current_app.config["EVENT_STARTS_AT"]:
        raise BusinessError("イベントはまだ開始していません。")
    if now >= current_app.config["EVENT_ENDS_AT"]:
        labels = {
            "register": "新規登録", "draw": "描画開始", "listing": "出品・再出品",
            "stream": "配信開始",
        }
        raise BusinessError(
            f"イベント終了のため、{labels.get(operation, '新規操作')}は受付終了です。"
        )
    return True
