"""1 日開催のイベント終了判定。"""

from flask import current_app

from ..clock import utcnow
from ..constants import EVENT_OPERATION_LABELS
from .errors import EventClosedError


def event_ends_at():
    """設定されたイベント終了時刻（naive UTC）。未設定なら None。"""
    return current_app.config.get("EVENT_ENDS_AT")


def is_event_closed(now=None):
    """イベント終了時刻を過ぎているか。"""
    now = now or utcnow()
    ends_at = event_ends_at()
    return bool(ends_at and now >= ends_at)


def validate_event_operation(operation, now=None):
    """操作ごとの受付期限を検証する。

    イベント終了後は新規登録・描画開始・出品・再出品を拒否する。
    ログイン・閲覧・ダウンロードは停止まで提供する。
    """
    if is_event_closed(now):
        label = EVENT_OPERATION_LABELS.get(operation, operation)
        raise EventClosedError(
            f"イベントは終了しました。{label}は受け付けていません。"
        )
