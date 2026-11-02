"""作品（下書き）の作成・正式保存・出品情報の編集。

仕様決定事項2・3章：
- 開始後の制限時間変更は不可。期限はサーバー側で管理する
- 完成・期限で描画を固定し、PNG とレイヤー ZIP の両方の保存に成功して
  初めて正式保存成功とする
- 保存後の加筆は認めない
"""

from __future__ import annotations

from datetime import timedelta

from flask import current_app

from app.extensions import db
from app.models.artwork import Artwork, DrawingSession
from app.services.errors import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.services.image_service import decode_data_url, save_png, validate_png
from app.services.layer_service import save_layer_archive, validate_layer_assets
from app.services.point_service import grant_draw_bonus
from app.utils import jst_date_key, utcnow


def create_draft(user, title: str = "") -> Artwork:
    """作者の下書き作品を作成する。"""
    artwork = Artwork(
        artist_id=user.id,
        title=title or "",
        description="",
        status="draft",
    )
    db.session.add(artwork)
    db.session.flush()
    return artwork


def start_drawing_session(user, duration_seconds: int) -> tuple[Artwork, DrawingSession]:
    """描画開始の記録を作る。

    制限時間は 10秒・30秒・1分・5分から選べ、開始後は変更しない。
    """
    allowed = tuple(current_app.config["DRAW_DURATION_SECONDS"])
    try:
        seconds = int(duration_seconds)
    except (TypeError, ValueError) as exc:
        raise ValidationError("描画時間を選択してください。") from exc
    if seconds not in allowed:
        raise ValidationError("描画時間は 10秒・30秒・1分・5分から選択してください。")

    artwork = create_draft(user)
    now = utcnow()
    session = DrawingSession(
        artwork_id=artwork.id,
        user_id=user.id,
        duration_seconds=seconds,
        started_at=now,
        deadline_at=now + timedelta(seconds=seconds),
        status="active",
    )
    db.session.add(session)
    db.session.flush()
    return artwork, session


def get_artwork(artwork_id: int) -> Artwork:
    """作品を 1 件取得する。"""
    artwork = Artwork.query.get(artwork_id)
    if artwork is None:
        raise NotFoundError("作品が見つかりません。")
    return artwork


def get_owned_artwork(artwork_id: int, user) -> Artwork:
    """作者本人にだけ作品を返す。"""
    artwork = get_artwork(artwork_id)
    if artwork.artist_id != user.id:
        raise PermissionDeniedError("この作品を操作する権限がありません。")
    return artwork


def list_user_drafts(user) -> list[Artwork]:
    """本人の下書き一覧を取得する。"""
    return (
        Artwork.query.filter_by(artist_id=user.id, status="draft")
        .order_by(Artwork.created_at.desc(), Artwork.id.desc())
        .all()
    )


def list_user_listings(user) -> list[Artwork]:
    """本人が出品した作品（公開済み）の一覧を取得する。"""
    return (
        Artwork.query.filter(
            Artwork.artist_id == user.id, Artwork.status.in_(("listed", "sold"))
        )
        .order_by(Artwork.created_at.desc(), Artwork.id.desc())
        .all()
    )


def update_draft_metadata(user, artwork, title: str, description: str) -> Artwork:
    """作者本人が出品情報（タイトル・説明）だけを更新する。

    保存後の加筆は認めないため、画像は変更しない。
    """
    if artwork.artist_id != user.id:
        raise PermissionDeniedError("この作品を操作する権限がありません。")
    if artwork.status != "draft":
        raise BusinessRuleError("出品済みの作品は出品情報を変更できません。")
    artwork.title = (title or "").strip()[:200]
    artwork.description = (description or "").strip()
    db.session.flush()
    return artwork


def _resolve_grace_until(session: DrawingSession) -> object:
    """保存猶予の期限を返す（未固定なら期限＋猶予）。"""
    if session.save_grace_until is not None:
        return session.save_grace_until
    grace = int(current_app.config["SAVE_GRACE_SECONDS"])
    return session.deadline_at + timedelta(seconds=grace)


def save_draft_assets(user, artwork, payload: dict) -> Artwork:
    """合成 PNG とレイヤー ZIP を保存して正式保存を完了する。

    検証は保存前にすべて行う。保存済みの作品には再保存しない。
    """
    if artwork.artist_id != user.id:
        raise PermissionDeniedError("この作品を操作する権限がありません。")
    if artwork.status != "draft":
        raise BusinessRuleError("出品済みの作品には保存できません。")
    if artwork.save_completed_at is not None:
        raise ConflictError("この作品は既に保存済みです。加筆はできません。")

    session = artwork.drawing_session
    if session is None:
        raise BusinessRuleError("描画セッションが見つかりません。")

    now = utcnow()
    if now > _resolve_grace_until(session):
        raise BusinessRuleError(
            "保存猶予が切れました。この作品は出品できません。"
        )
    if session.finished_at is None and now >= session.deadline_at:
        # 期限到達で描画を固定する（保存だけ猶予内なら受け付ける）
        session.finished_at = session.deadline_at
        session.status = "fixed"
        session.save_grace_until = session.deadline_at + timedelta(
            seconds=int(current_app.config["SAVE_GRACE_SECONDS"])
        )

    raw_png = decode_data_url((payload or {}).get("png") or "")
    validate_png(raw_png)

    layers = validate_layer_assets((payload or {}).get("layers") or [])

    image_path = save_png(raw_png)
    archive_path = save_layer_archive(layers, manifest=(payload or {}).get("manifest"))

    artwork.image_path = image_path
    artwork.layer_archive_path = archive_path
    artwork.save_completed_at = now
    session.status = "saved"
    session.finished_at = session.finished_at or now
    db.session.flush()

    grant_draw_bonus(
        user,
        int(current_app.config["BONUS_DRAW_POINTS"]),
        bonus_date=jst_date_key(now),
    )
    return artwork
