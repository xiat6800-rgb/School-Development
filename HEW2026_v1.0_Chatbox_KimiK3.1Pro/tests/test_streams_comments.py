from datetime import datetime, timedelta

import pytest

from app.extensions import db
from app.models import StreamComment
from app.services.artwork_service import create_draft, finish_drawing_session
from app.services.comment_service import (
    admin_visible_body, calculate_body_purge_at, create_comment, delete_comment,
    hide_comment, purge_expired_comment_bodies,
)
from app.services.common import BusinessError
from app.services.stream_service import (
    can_resume_stream, create_stream, end_stream, pause_stream, resume_stream,
    start_stream,
)
from tests.conftest import create_user


def make_stream(artist, now=None):
    artwork = create_draft(artist, 300, now=now)
    stream = create_stream(artwork)
    return artwork, stream


def test_one_artwork_one_stream_and_end_is_terminal(app):
    with app.app_context():
        artist = create_user("artist")
        artwork, stream = make_stream(artist)
        with pytest.raises(BusinessError):
            create_stream(artwork)
        start_stream(stream, artist)
        end_stream(stream, artist)
        with pytest.raises(BusinessError):
            start_stream(stream, artist)
        assert stream.status == "ended"


def test_resume_requires_pause_within_ten_minutes_and_drawing_deadline(app):
    with app.app_context():
        artist = create_user("artist")
        artwork, stream = make_stream(artist)
        now = artwork.drawing_started_at
        start_stream(stream, artist, now=now)
        pause_stream(stream, artist, now=now + timedelta(seconds=5))
        assert can_resume_stream(stream, now + timedelta(minutes=4))
        assert not can_resume_stream(stream, now + timedelta(minutes=11))
        resume_stream(stream, artist, now=now + timedelta(minutes=1))
        assert stream.status == "live"
        assert not can_resume_stream(stream, artwork.drawing_ends_at)


def test_comment_rules_and_public_body_immediately_hidden(app):
    with app.app_context():
        artist = create_user("artist")
        guest = create_user("guest")
        artwork, stream = make_stream(artist)
        start_stream(stream, artist)
        comment = create_comment(stream.id, guest, "  素敵です  ")
        assert comment.body == "素敵です"
        with pytest.raises(BusinessError):
            create_comment(stream.id, guest, "連投")
        with pytest.raises(BusinessError):
            create_comment(stream.id, guest, "   ", now=comment.created_at + timedelta(seconds=3))
        with pytest.raises(BusinessError):
            create_comment(stream.id, guest, "x" * 201, now=comment.created_at + timedelta(seconds=3))
        hide_comment(comment, artist, "モデレーション")
        assert comment.status == "hidden"
        assert comment.purge_body_at is not None
        assert len(comment.audits) == 1


def test_comment_only_live_and_author_delete(app):
    with app.app_context():
        artist = create_user("artist")
        guest = create_user("guest")
        artwork, stream = make_stream(artist)
        with pytest.raises(BusinessError):
            create_comment(stream.id, guest, "配信前")
        start_stream(stream, artist)
        pause_stream(stream, artist)
        with pytest.raises(BusinessError):
            create_comment(stream.id, guest, "中断中")
        resume_stream(stream, artist)
        comment = create_comment(stream.id, guest, "投稿")
        with pytest.raises(BusinessError):
            delete_comment(comment, artist)
        delete_comment(comment, guest)
        assert comment.status == "deleted"


def test_jst_calendar_month_handles_month_end_and_purge(app):
    # JST 2026/03/31 09:00 = UTC 2026/03/30 15:00。翌月同日なしで4/30。
    moderated = datetime(2026, 3, 30, 15, 0)
    assert calculate_body_purge_at(moderated) == datetime(2026, 4, 29, 15, 0)
    with app.app_context():
        artist = create_user("artist")
        guest = create_user("guest")
        artwork, stream = make_stream(artist)
        start_stream(stream, artist)
        comment = create_comment(stream.id, guest, "消去対象")
        delete_comment(comment, guest)
        comment.purge_body_at = datetime(2026, 1, 1)
        assert admin_visible_body(comment, now=datetime(2026, 1, 1)) is None
        assert purge_expired_comment_bodies(now=datetime(2026, 1, 2)) == 1
        assert comment.body is None
        assert len(comment.audits) == 1


def test_finish_drawing_also_ends_stream(app):
    with app.app_context():
        artist = create_user("artist")
        artwork, stream = make_stream(artist)
        start_stream(stream, artist)
        finish_drawing_session(artwork)
        assert stream.status == "ended"
        assert artwork.finished_at is not None
        assert artwork.save_grace_ends_at is not None
