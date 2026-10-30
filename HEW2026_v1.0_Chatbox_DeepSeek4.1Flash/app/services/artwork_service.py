"""描画セッション・正式保存・下書き管理。"""

from datetime import timedelta

from flask import current_app

from ..clock import utcnow
from ..constants import (
    ARTWORK_STATUS_DRAFT,
    ARTWORK_STATUS_SOLD,
    BONUS_DAILY_SAVE,
    EVENT_OPERATION_DRAW_START,
)
from ..extensions import db
from ..models import Artwork
from . import event_service, image_service, layer_service, point_service
from .errors import SaveError, ValidationError


def get_artwork(artwork_id):
    return db.session.get(Artwork, int(artwork_id))


def create_draft(artist, title=None):
    """画像未登録の下書き作品を作成する。"""
    artwork = Artwork(
        artist_id=artist.id,
        title=(title or "")[:200],
        status=ARTWORK_STATUS_DRAFT,
    )
    db.session.add(artwork)
    db.session.flush()
    return artwork


def start_drawing_session(artist, duration_seconds, now=None):
    """制限時間を選んで描画を開始する。開始後の変更は不可。"""
    now = now or utcnow()
    config = current_app.config
    try:
        duration = int(duration_seconds)
    except (TypeError, ValueError):
        raise ValidationError("描画時間を選択してください。")
    if duration not in config["DRAWING_DURATIONS"]:
        raise ValidationError(
            "描画時間は10秒・30秒・1分・5分から選択してください。"
        )
    event_service.validate_event_operation(EVENT_OPERATION_DRAW_START, now)

    artwork = create_draft(artist)
    artwork.canvas_size = config["CANVAS_SIZE"]
    artwork.drawing_duration_seconds = duration
    artwork.drawing_started_at = now
    artwork.drawing_deadline = now + timedelta(seconds=duration)
    artwork.save_deadline = artwork.drawing_deadline + timedelta(
        seconds=config["SAVE_GRACE_SECONDS"]
    )
    db.session.commit()
    return artwork


def finish_drawing_session(artwork, now=None):
    """完成操作または期限到達で描画データを固定する。"""
    now = now or utcnow()
    if artwork.drawing_finished_at is None:
        artwork.drawing_finished_at = now
    if artwork.save_deadline is None:
        artwork.save_deadline = now + timedelta(
            seconds=current_app.config["SAVE_GRACE_SECONDS"]
        )
    db.session.flush()
    return artwork


def save_draft_assets(artwork, composite_png, layer_files, manifest_raw, now=None):
    """合成 PNG とレイヤー ZIP の両方を保存して正式保存を完了する。

    再送では二重に作品を作らず、ボーナスも重複付与しない。
    """
    now = now or utcnow()
    config = current_app.config

    if artwork.status == ARTWORK_STATUS_SOLD:
        raise SaveError("落札済みの作品は差し替えできません。")
    if artwork.is_saved:
        raise SaveError("この作品は正式保存済みです。加筆・差し替えはできません。")
    if artwork.save_deadline is None:
        raise SaveError("描画セッションが開始されていません。")
    if now > artwork.save_deadline:
        raise SaveError(
            "保存の猶予（60秒）を過ぎました。この作品は出品できません。"
        )

    image_service.validate_png(
        composite_png,
        max_bytes=config["MAX_COMPOSITE_PNG_BYTES"],
        expected_size=config["CANVAS_SIZE"],
        label="合成PNG",
    )
    manifest = layer_service.parse_manifest(manifest_raw)
    layer_service.validate_layers(layer_files, manifest)

    png_path = image_service.save_png(
        composite_png, config["UPLOAD_ROOT"], subdir="composite"
    )
    archive = layer_service.build_layer_archive(layer_files, manifest)
    zip_path = layer_service.save_layer_archive(archive, config["UPLOAD_ROOT"])

    artwork.image_path = png_path
    artwork.layer_zip_path = zip_path
    artwork.asset_saved_at = now
    if artwork.drawing_finished_at is None:
        finish_drawing_session(artwork, now)
    db.session.flush()

    grant = point_service.grant_bonus_points(artwork.artist, BONUS_DAILY_SAVE, now)
    db.session.commit()
    return artwork, grant


def list_user_drafts(user_id):
    """本人の下書き一覧を新しい順に取得する。"""
    return db.session.scalars(
        db.select(Artwork)
        .where(
            Artwork.artist_id == user_id,
            Artwork.status == ARTWORK_STATUS_DRAFT,
        )
        .order_by(Artwork.created_at.desc())
    ).all()


def update_draft_metadata(artwork, title, description):
    """作者本人がタイトル・説明を更新する。保存後の加筆は認めない。"""
    title = (title or "").strip()
    if not title:
        raise ValidationError("タイトルを入力してください。")
    if len(title) > 200:
        raise ValidationError("タイトルは200文字以内で入力してください。")
    artwork.title = title
    artwork.description = (description or "").strip()[:2000] or None
    db.session.commit()
    return artwork
