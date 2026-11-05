"""イベント期間サービス。1日開催の終了日時と操作受付期限を検証する。"""
from datetime import datetime, timedelta, timezone

from flask import current_app


class EventClosedError(Exception):
    """イベント終了で受付不可の場合に発生する。"""


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_event_end():
    """設定されたイベント終了日時（UTC）を返す。未設定なら None。"""
    return current_app.config.get("EVENT_END_UTC")


def is_event_ended(now=None):
    end = get_event_end()
    if end is None:
        return False
    return (now or utcnow()) >= end


def validate_event_operation(operation):
    """イベント終了後は新規登録・描画開始・出品・再出品を拒否する。"""
    if is_event_ended():
        raise EventClosedError(
            f"イベントが終了したため、{operation}は受付できません。"
        )


def ensure_auction_duration(minutes, now=None):
    """終了日時までに開催時間を確保できるか検証する。残り5分未満は不可。"""
    end = get_event_end()
    if end is None:
        return
    now = now or utcnow()
    remaining = (end - now).total_seconds()
    margin = current_app.config["MIN_AUCTION_MARGIN_SECONDS"]
    if remaining < margin or remaining < minutes * 60:
        raise EventClosedError(
            "イベント終了までに開催時間を確保できないため、出品できません。"
        )
