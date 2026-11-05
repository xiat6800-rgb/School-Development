"""作品（下書き）の作成・描画セッション・正式保存。"""

from datetime import timedelta

from flask import current_app

from app.extensions import db
from app.models import Artwork
from app.services import image_service, layer_service, point_service
from app.services.event_service import get_server_now, validate_event_operation

ALLOWED_DRAWING_DURATIONS = (10, 30, 60, 300)


class DrawingError(Exception):
    """描画セッション・保存の条件を満たさない。"""


def create_draft(artist, duration_seconds):
    """描画開始。開始時刻と変更不可の期限をサーバーで記録する。"""
    validate_event_operation("draw_start")
    if duration_seconds not in ALLOWED_DRAWING_DURATIONS:
        raise DrawingError("描画時間は10秒・30秒・1分・5分から選んでください。")
    now = get_server_now()
    artwork = Artwork(
        artist_id=artist.id,
        title="無題の作品",
        status=Artwork.STATUS_DRAFT,
        duration_seconds=duration_seconds,
        drawing_started_at=now,
        drawing_deadline=now + timedelta(seconds=duration_seconds),
    )
    db.session.add(artwork)
    db.session.commit()
    return artwork


def finish_drawing_session(artwork, when=None):
    """完成操作で描画を固定する。期限到達は drawing_deadline をそのまま使う。"""
    if artwork.frozen_at is not None:
        return artwork.frozen_at
    artwork.frozen_at = when or get_server_now()
    return artwork.frozen_at


def _freeze_reference(artwork):
    return artwork.frozen_at or artwork.drawing_deadline


def can_save_assets(artwork):
    """保存猶予（固定後60秒）内かどうか。"""
    if artwork.is_formally_saved:
        return True
    reference = _freeze_reference(artwork)
    if reference is None:
        return True
    grace = current_app.config["SAVE_GRACE_SECONDS"]
    return get_server_now() <= reference + timedelta(seconds=grace)


def save_draft_assets(artwork, image_file, layer_files, manifest, finished=True):
    """合成PNGとレイヤーZIPの両方を保存して正式保存を完了する。

    両方が成功した時点で正式保存成功。再送時は既存結果を返し、
    重複作品・重複ボーナスを防ぐ。戻り値: (artwork, granted_bonus)
    """
    if artwork.is_formally_saved:
        return artwork, False
    if not can_save_assets(artwork):
        raise DrawingError("保存猶予を過ぎたため保存できません。")
    if finished:
        finish_drawing_session(artwork)

    image_service.validate_png(image_file)
    layer_bytes = layer_service.validate_layer_assets(layer_files, manifest)

    png_path = image_service.save_png(image_file, artwork.id)
    zip_path = layer_service.save_layer_archive(layer_bytes, manifest, artwork.id)

    artwork.image_path = png_path
    artwork.layers_zip_path = zip_path
    artwork.saved_at = get_server_now()

    granted = point_service.grant_drawing_save_bonus(artwork.artist)
    db.session.commit()
    return artwork, granted


def list_user_drafts(artist):
    return (
        Artwork.query.filter_by(artist_id=artist.id, status=Artwork.STATUS_DRAFT)
        .order_by(Artwork.created_at.desc())
        .all()
    )


def list_user_artworks(artist):
    return (
        Artwork.query.filter_by(artist_id=artist.id)
        .order_by(Artwork.created_at.desc())
        .all()
    )


def get_artwork_for_owner(artwork_id, user):
    artwork = db.session.get(Artwork, artwork_id)
    if artwork is None or artwork.artist_id != user.id:
        return None
    return artwork


def update_draft_metadata(artwork, title=None, description=None):
    """出品情報（タイトル・説明）だけを更新する。画像の差し替えは不可。"""
    if title is not None:
        title = title.strip()
        if not title:
            raise DrawingError("タイトルを入力してください。")
        if len(title) > 200:
            raise DrawingError("タイトルは200文字以内にしてください。")
        artwork.title = title
    if description is not None:
        artwork.description = description.strip() or None
    db.session.commit()
    return artwork
