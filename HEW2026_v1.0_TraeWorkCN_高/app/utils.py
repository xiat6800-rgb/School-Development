"""日時変換・表示用の小さなユーティリティ。

DB には UTC の naive datetime を保存し、画面では日本時間（UTC+9）で表示する。
"""
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9), "JST")


def utcnow():
    """naive な UTC 現在時刻（DB 保存用）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_jst(value):
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc).astimezone(JST)


def format_jst(value, fmt="%Y/%m/%d %H:%M"):
    converted = to_jst(value)
    return converted.strftime(fmt) if converted else "-"


def from_jst_input(value):
    """<input type="datetime-local"> の日本時間を UTC naive に変換する。"""
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            local = datetime.strptime(value, fmt)
            return (local - timedelta(hours=9)).replace(tzinfo=None)
        except ValueError:
            continue
    return None


def remaining_seconds(end_time):
    if end_time is None:
        return 0
    return max(0, int((end_time - utcnow()).total_seconds()))


def format_remaining(end_time):
    seconds = remaining_seconds(end_time)
    if seconds <= 0:
        return "終了"
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)
    if days:
        return f"{days}日 {hours}時間 {minutes}分"
    if hours:
        return f"{hours}時間 {minutes}分 {secs}秒"
    return f"{minutes}分 {secs}秒"


def safe_next(default_endpoint="/"):
    """リダイレクト先はアプリ内の相対パスだけ許可する（オープンリダイレクト対策）。"""
    from flask import request

    target = request.form.get("next") or request.args.get("next")
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return default_endpoint
