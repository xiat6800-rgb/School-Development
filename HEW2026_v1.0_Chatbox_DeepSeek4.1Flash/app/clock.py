"""時刻ユーティリティ。

DB には naive UTC で保存し、画面には日本時間で表示する。
"""

from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9), "JST")
DISPLAY_FORMAT = "%Y/%m/%d %H:%M"


def utcnow():
    """現在時刻を naive UTC で返す。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_jst(value):
    """naive UTC を aware JST へ変換する。"""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(JST)


def format_jst(value, fmt=DISPLAY_FORMAT):
    """画面表示用に日本時間で整形する。"""
    if value is None:
        return "—"
    return to_jst(value).strftime(fmt)


def jst_date(value=None):
    """日本時間の暦日を返す。"""
    return to_jst(value or utcnow()).date()


def seconds_between(start, end):
    """end - start を秒で返す。どちらかが None なら None。"""
    if start is None or end is None:
        return None
    return int((end - start).total_seconds())


def add_months_jst(value, months=1):
    """日本時間基準で暦月を加算し、UTC へ戻す。

    翌月に同日がない場合は月末の同時刻を返す。
    配信コメントの本文消去期限の計算に使用する（Ver1 追加仕様）。
    """
    if value is None:
        return None
    local = to_jst(value)
    year = local.year + (local.month - 1 + months) // 12
    month = (local.month - 1 + months) % 12 + 1

    if month == 12:
        next_month = datetime(year + 1, 1, 1, tzinfo=JST)
    else:
        next_month = datetime(year, month + 1, 1, tzinfo=JST)
    last_day = (next_month - timedelta(days=1)).day
    day = min(local.day, last_day)
    shifted = local.replace(year=year, month=month, day=day)
    return shifted.astimezone(timezone.utc).replace(tzinfo=None)
