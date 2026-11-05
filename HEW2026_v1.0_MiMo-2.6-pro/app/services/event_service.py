"""1日開催イベントの受付期限を管理する。"""

from datetime import datetime, timezone

from flask import current_app


class EventClosedError(Exception):
    """イベント終了後に受付不可の操作が要求された。"""


ALLOWED_OPERATIONS = ("register", "draw_start", "list")


def get_event_end_at():
    return current_app.config.get("EVENT_END_AT")


def get_server_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def validate_event_operation(operation):
    """操作がイベント終了前かを検証し、終了後なら EventClosedError。"""
    if operation not in ALLOWED_OPERATIONS:
        raise ValueError(f"unknown operation: {operation}")
    end_at = get_event_end_at()
    if end_at is not None and get_server_now() >= end_at:
        raise EventClosedError("イベントは終了しました。")


def remaining_seconds():
    end_at = get_event_end_at()
    if end_at is None:
        return None
    delta = end_at - get_server_now()
    return delta.total_seconds()
