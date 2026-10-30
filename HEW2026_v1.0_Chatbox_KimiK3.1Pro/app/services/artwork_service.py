from datetime import timedelta

from app.constants import DRAWING_DURATIONS, SAVE_GRACE_SECONDS
from app.extensions import db
from app.models import Artwork
from app.services.common import BusinessError
from app.services.event_service import validate_event_operation
from app.services.image_service import save_png_and_archive
from app.services.point_service import grant_bonus_points
from app.utils import utcnow


def create_draft(artist, duration_seconds, title="無題", now=None):
    validate_event_operation("draw", now)
    if duration_seconds not in DRAWING_DURATIONS:
        raise BusinessError("描画時間は10秒・30秒・1分・5分から選んでください。")
    now = now or utcnow()
    artwork = Artwork(
        artist=artist,
        title=(title or "無題").strip()[:200] or "無題",
        duration_seconds=duration_seconds,
        drawing_started_at=now,
        drawing_ends_at=now + timedelta(seconds=duration_seconds),
        status="draft",
        is_public=False,
    )
    db.session.add(artwork)
    db.session.flush()
    return artwork


def finish_drawing_session(artwork, now=None):
    now = now or utcnow()
    if artwork.is_saved:
        raise BusinessError("正式保存済みの作品は編集できません。")
    if artwork.finished_at is None:
        artwork.finished_at = now
        grace_base = min(now, artwork.drawing_ends_at)
        artwork.save_grace_ends_at = grace_base + timedelta(
            seconds=SAVE_GRACE_SECONDS
        )
    if artwork.stream and artwork.stream.status != "ended":
        from app.services.stream_service import end_stream
        end_stream(artwork.stream, artwork.artist, "drawing_finished", now=now)
    db.session.flush()
    return artwork


def save_draft_assets(artwork, png_data, archive_data, now=None):
    now = now or utcnow()
    if artwork.is_saved:
        return artwork, False
    finish_drawing_session(artwork, now=now)
    if now > artwork.save_grace_ends_at:
        raise BusinessError(
            "60秒の保存猶予を過ぎました。端末保存は可能ですが、出品と描画ボーナスはできません。"
        )
    png_path, archive_path = save_png_and_archive(png_data, archive_data)
    artwork.image_path = png_path
    artwork.archive_path = archive_path
    artwork.saved_at = now
    db.session.flush()
    grant_bonus_points(artwork.artist, "daily_drawing", artwork=artwork)
    db.session.flush()
    return artwork, True


def list_user_drafts(user):
    return Artwork.query.filter_by(artist_id=user.id, status="draft").order_by(
        Artwork.id.desc()
    ).all()


def get_owned_artwork(artwork_id, user):
    artwork = db.session.get(Artwork, artwork_id)
    if not artwork or artwork.artist_id != user.id:
        raise BusinessError("自分の下書きだけを操作できます。")
    return artwork
