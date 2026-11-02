"""共通ユーティリティ。

時刻はすべて UTC で保存し、画面表示時に日本時間へ変換する。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
UTC = timezone.utc


def utcnow() -> datetime:
    """タイムゾーン情報を持たない UTC 現在時刻を返す。"""
    return datetime.now(UTC).replace(tzinfo=None)


def to_jst(moment: datetime | None) -> datetime | None:
    """保存済みの UTC 時刻を日本時間へ変換する。"""
    if moment is None:
        return None
    return moment.replace(tzinfo=UTC).astimezone(JST)


def format_jst(moment: datetime | None, pattern: str = "%Y/%m/%d %H:%M") -> str:
    """日本時間で文字列化する。None は空文字。"""
    converted = to_jst(moment)
    if converted is None:
        return ""
    return converted.strftime(pattern)


def jst_date_key(moment: datetime | None = None) -> str:
    """日本時間の暦日キーを返す（描画ボーナスの1日1回判定に使う）。"""
    converted = to_jst(moment or utcnow())
    return converted.strftime("%Y-%m-%d")


def remaining_seconds(end_time: datetime | None) -> int:
    """終了日時までの残り秒数を返す。期限切れは 0。"""
    if end_time is None:
        return 0
    delta = end_time - utcnow()
    return max(0, int(delta.total_seconds()))


def is_expired(end_time: datetime | None) -> bool:
    """終了日時を過ぎているかを返す。"""
    if end_time is None:
        return False
    return utcnow() >= end_time


def format_remaining(end_time: datetime | None) -> str:
    """残り時間を「MM:SS」形式で返す。"""
    seconds = remaining_seconds(end_time)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"
