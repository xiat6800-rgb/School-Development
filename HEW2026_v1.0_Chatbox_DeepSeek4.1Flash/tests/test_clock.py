"""時刻ユーティリティの単体テスト.

DB も Flask も要らない純粋な関数なので、CI で一番速く回る。
「時間に依存する処理」は現場でバグの温床になるので、
境界値（月末・うるう年・時差）を意識して書く。
"""

from datetime import datetime, timedelta, timezone

from app.clock import add_months_jst, format_jst, seconds_between, to_jst, utcnow


def test_utcnow_is_naive_utc():
    now = utcnow()
    assert now.tzinfo is None
    # naive UTC が返っていること（aware の now から tz を落として比較）
    reference = datetime.now(timezone.utc).replace(tzinfo=None)
    assert abs((now - reference).total_seconds()) < 5


def test_to_jst_adds_nine_hours():
    utc = datetime(2026, 1, 1, 0, 0, 0)  # naive UTC
    jst = to_jst(utc)
    assert jst.hour == 9
    assert jst.utcoffset() == timedelta(hours=9)


def test_format_jst_returns_dash_for_none():
    assert format_jst(None) == "—"


def test_seconds_between_handles_none():
    assert seconds_between(None, utcnow()) is None
    start = datetime(2026, 1, 1, 0, 0, 0)
    assert seconds_between(start, start + timedelta(seconds=90)) == 90


def test_add_months_clamps_to_month_end():
    """1/31 の 1 か月後は 2/28（2026 年はうるう年ではない）になる。"""

    jan31_jst_9am = (
        datetime(2026, 1, 31, 0, 0, 0)
        .replace(tzinfo=timezone.utc)
        .astimezone(timezone(timedelta(hours=9)))
    )
    utc_input = jan31_jst_9am.astimezone(timezone.utc).replace(tzinfo=None)

    result = add_months_jst(utc_input, months=1)
    result_jst = to_jst(result)

    assert (result_jst.month, result_jst.day) == (2, 28)


def test_add_months_handles_december_rollover():
    dec15 = datetime(2026, 12, 15, 3, 0, 0)
    result_jst = to_jst(add_months_jst(dec15, months=1))
    assert (result_jst.year, result_jst.month, result_jst.day) == (2027, 1, 15)
