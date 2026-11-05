"""作品サービス。描画セッション・下書き・正式保存を管理する。"""
from datetime import datetime, timedelta, timezone

from flask import current_app

from ..extensions import db
from ..models.artwork import Artwork
from . import event_service, image_service, layer_service, point_service


class ArtworkError(Exception):
    """作品操作が業務ルールに反する場合に発生する。"""


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_draft(artist):
    """作者の下書き作品（画像なし）を作成する。"""
    artwork = Artwork(artist_id=artist.id, title="", status="draft")
    db.session.add(artwork)
    db.session.commit()
    return artwork


def start_drawing_session(artwork, duration_seconds):
    """描画開始時刻と変更不可の期限をサーバー時刻で記録する。"""
    allowed = current_app.config["ALLOWED_DRAWING_DURATIONS"]
    if duration_seconds not in allowed:
        raise ArtworkError("描画時間は 10秒・30秒・1分・5分 から選んでください。")
    if artwork.drawing_started_at is not None:
        raise ArtworkError("開始後は制限時間を変更できません。")
    if artwork.is_saved:
        raise ArtworkError("保存済みの作品には加筆できません。")
    event_service.validate_event_operation("描画開始")
    now = utcnow()
    artwork.drawing_duration_seconds = duration_seconds
    artwork.drawing_started_at = now
    artwork.drawing_deadline = now + timedelta(seconds=duration_seconds)
    db.session.commit()
    return artwork


def finish_drawing_session(artwork):
    """完成操作で描画を固定する。期限後はデータを受け付けない。"""
    now = utcnow()
    grace = current_app.config["SAVE_GRACE_SECONDS"]
    if artwork.drawing_deadline and now > artwork.drawing_deadline + timedelta(seconds=grace):
        raise ArtworkError("保存猶予（60秒）を過ぎたため、正式保存できません。")


def save_draft_assets(artwork, png_bytes, zip_bytes):
    """PNG とレイヤーZIP の両方を保存して正式保存を完了する。

    両方の保存成功が条件。再送（保存済み）は成功を返し、
    作品の重複作成やボーナスの重複付与を防ぐ。
    """
    if artwork.is_saved:
        return artwork  # 冪等: 正式保存成功後の再送
    finish_drawing_session(artwork)

    filename = image_service.save_png(png_bytes)
    try:
        zip_name = layer_service.save_layer_archive(zip_bytes)
    except layer_service.InvalidLayerArchiveError:
        # 片方だけ保存して正式保存成功にしない
        _remove_file(filename)
        raise

    artwork.image_path = filename
    artwork.layer_zip_path = zip_name
    artwork.drawing_saved_at = utcnow()
    point_service.grant_bonus_points(
        artwork.artist,
        "draw_save",
        point_service.jst_today_key(artwork.artist_id),
    )
    db.session.commit()
    return artwork


def _remove_file(filename):
    from pathlib import Path

    path = Path(current_app.config["UPLOAD_FOLDER"]) / filename
    path.unlink(missing_ok=True)


def list_user_drafts(user):
    """本人の下書き一覧を取得する。"""
    return (
        Artwork.query.filter_by(artist_id=user.id, status="draft")
        .order_by(Artwork.created_at.desc())
        .all()
    )


def update_draft_metadata(artwork, title=None, description=None):
    """作者本人がタイトル・説明などの出品情報を更新する。加筆は不可。"""
    if title is not None:
        artwork.title = title[:200]
    if description is not None:
        artwork.description = description
    db.session.commit()
    return artwork


def can_download_asset(user, artwork):
    """原寸PNG・ZIPの取得権限: 作者、または落札確定済みの落札者。"""
    if not artwork.is_saved:
        return False
    if user.id == artwork.artist_id:
        return True
    for auction in artwork.auctions:
        if (
            auction.status == "ended"
            and auction.winner_id == user.id
            and auction.winner_bid_id is not None
        ):
            return True
    return False
