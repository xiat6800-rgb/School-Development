from flask import current_app

from app.constants import (
    STREAM_HEARTBEAT_TIMEOUT_SECONDS, STREAM_RESUME_SECONDS,
)
from app.extensions import db
from app.models import LiveStream
from app.services.common import BusinessError
from app.services.event_service import validate_event_operation
from app.services.image_service import save_stream_preview
from app.utils import utcnow


def create_stream(artwork):
    if artwork.stream:
        raise BusinessError("1作品に作成できる配信は1件だけです。")
    if artwork.is_saved:
        raise BusinessError("正式保存済み作品には配信を作成できません。")
    stream = LiveStream(artwork=artwork, status="ready")
    db.session.add(stream)
    db.session.flush()
    return stream


def _owned_stream(stream, user):
    if stream.artwork.artist_id != user.id:
        raise BusinessError("配信を操作できるのは作者本人だけです。")


def start_stream(stream, user, *, now=None):
    now = now or utcnow()
    _owned_stream(stream, user)
    validate_event_operation("stream", now)
    if stream.status != "ready":
        raise BusinessError("配信前の状態からのみ開始できます。終了後の再開はできません。")
    if now >= stream.artwork.drawing_ends_at or stream.artwork.finished_at:
        raise BusinessError("描画期限・完成後は配信を開始できません。")
    stream.status = "live"
    stream.started_at = now
    stream.last_heartbeat_at = now
    stream.disconnected_at = None
    return stream


def pause_stream(stream, user, *, now=None):
    now = now or utcnow()
    _owned_stream(stream, user)
    if stream.status != "live":
        return stream
    stream.status = "paused"
    stream.disconnected_at = now
    return stream


def can_resume_stream(stream, now=None):
    now = now or utcnow()
    return bool(
        stream.status == "paused"
        and stream.disconnected_at
        and (now - stream.disconnected_at).total_seconds() <= STREAM_RESUME_SECONDS
        and now < stream.artwork.drawing_ends_at
        and now < current_app.config["EVENT_ENDS_AT"]
        and not stream.artwork.finished_at
    )


def resume_stream(stream, user, *, now=None):
    now = now or utcnow()
    locked = LiveStream.query.filter_by(id=stream.id).with_for_update().first()
    _owned_stream(locked, user)
    if not can_resume_stream(locked, now):
        raise BusinessError("中断10分・描画期限・イベント期限を確認したため復帰できません。")
    locked.status = "live"
    locked.disconnected_at = None
    locked.last_heartbeat_at = now
    return locked


def end_stream(stream, user, reason="author_ended", *, now=None):
    now = now or utcnow()
    _owned_stream(stream, user)
    if stream.status == "ended":
        return stream
    stream.status = "ended"
    stream.ended_at = now
    stream.end_reason = reason
    stream.disconnected_at = None
    return stream


def heartbeat_stream(stream, user, *, now=None):
    now = now or utcnow()
    _owned_stream(stream, user)
    if stream.status != "live" or now >= stream.artwork.drawing_ends_at:
        raise BusinessError("配信中ではありません。")
    stream.last_heartbeat_at = now
    return stream


def update_stream_preview(stream, user, png_data, *, now=None):
    heartbeat_stream(stream, user, now=now)
    stream.preview_path = save_stream_preview(png_data)
    return stream


def close_stale_streams(*, now=None):
    now = now or utcnow()
    streams = LiveStream.query.filter(LiveStream.status != "ended").all()
    paused = 0
    ended = 0
    for stream in streams:
        if (
            now >= stream.artwork.drawing_ends_at
            or now >= current_app.config["EVENT_ENDS_AT"]
            or stream.artwork.finished_at
        ):
            stream.status = "ended"
            stream.ended_at = now
            stream.end_reason = "deadline_or_event"
            ended += 1
            continue
        if stream.status == "live" and stream.last_heartbeat_at:
            silent = (now - stream.last_heartbeat_at).total_seconds()
            if silent > STREAM_HEARTBEAT_TIMEOUT_SECONDS:
                stream.status = "paused"
                stream.disconnected_at = stream.last_heartbeat_at
                paused += 1
        if stream.status == "paused" and stream.disconnected_at:
            paused_seconds = (now - stream.disconnected_at).total_seconds()
            if paused_seconds > STREAM_RESUME_SECONDS:
                stream.status = "ended"
                stream.ended_at = now
                stream.end_reason = "disconnect_timeout"
                ended += 1
    db.session.flush()
    return {"paused": paused, "ended": ended}
