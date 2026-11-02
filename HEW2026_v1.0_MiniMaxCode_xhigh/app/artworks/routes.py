"""描画・PNG とレイヤー ZIP の保存・出品設定。

- 制限時間（10秒/30秒/1分/5分）は開始時に確定し、開始後は変更しない
- 正式保存は「合成 PNG」と「レイヤー ZIP」の両方の保存成功で成立する
- 保存後の加筆は認めない（出品情報の編集のみ可能）
"""

from __future__ import annotations

from flask import (
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required

from app.artworks import artworks_bp
from app.config import upload_root
from app.extensions import db
from app.models.artwork import Artwork
from app.services import artwork_service, auction_service, tag_service
from app.services.errors import ServiceError


@artworks_bp.route("/artworks/draw", methods=["GET"])
@login_required
def show_drawing_setup():
    """描画時間を選択する画面を表示する。"""
    return render_template(
        "artworks/draw_setup.html",
        durations=current_app.config["DRAW_DURATION_SECONDS"],
    )


@artworks_bp.route("/artworks/draw/start", methods=["POST"])
@login_required
def start_drawing():
    """描画を開始し、下書きと描画セッションを作る。"""
    try:
        artwork, session = artwork_service.start_drawing_session(
            current_user, request.form.get("duration_seconds")
        )
        db.session.commit()
    except ServiceError as error:
        db.session.rollback()
        flash(error.message, "error")
        return redirect(url_for("artworks.show_drawing_setup"))

    return redirect(url_for("artworks.show_canvas", artwork_id=artwork.id))


@artworks_bp.route("/artworks/<int:artwork_id>/canvas", methods=["GET"])
@login_required
def show_canvas(artwork_id: int):
    """描画画面を表示する。"""
    artwork = artwork_service.get_owned_artwork(artwork_id, current_user)
    session = artwork.drawing_session
    if session is None:
        flash("描画セッションが見つかりません。", "error")
        return redirect(url_for("artworks.show_drawing_setup"))
    if artwork.save_completed_at is not None:
        flash("保存済みの作品には加筆できません。", "error")
        return redirect(url_for("artworks.show_listing_form", artwork_id=artwork.id))

    return render_template(
        "artworks/canvas.html",
        artwork=artwork,
        session=session,
        deadline_iso=session.deadline_at.strftime("%Y-%m-%dT%H:%M:%S"),
        grace_seconds=current_app.config["SAVE_GRACE_SECONDS"],
        canvas_size=current_app.config["CANVAS_SIZE"],
    )


@artworks_bp.route("/artworks/<int:artwork_id>/save", methods=["POST"])
@login_required
def save_draft(artwork_id: int):
    """合成 PNG とレイヤー ZIP を受け取って正式保存する。"""
    payload = request.get_json(silent=True) or {}
    try:
        artwork = artwork_service.get_owned_artwork(artwork_id, current_user)
        artwork_service.save_draft_assets(current_user, artwork, payload)
        db.session.commit()
    except ServiceError as error:
        db.session.rollback()
        return jsonify({"ok": False, "message": error.message}), error.status_code
    except Exception:  # pragma: no cover - 予期しない失敗
        db.session.rollback()
        return jsonify({"ok": False, "message": "保存に失敗しました。"}), 500

    return jsonify(
        {
            "ok": True,
            "artwork_id": artwork.id,
            "listing_url": url_for("artworks.show_listing_form", artwork_id=artwork.id),
        }
    )


@artworks_bp.route("/artworks/<int:artwork_id>/image")
def show_artwork_image(artwork_id: int):
    """公開用の画像を表示する。下書きは作者本人にだけ見せる。"""
    artwork = Artwork.query.get(artwork_id)
    if artwork is None or not artwork.image_path:
        return ("Not Found", 404)
    if not artwork.is_public and not _is_owner(artwork):
        return ("Not Found", 404)

    return send_from_directory(
        upload_root(current_app.config["UPLOAD_FOLDER"]),
        artwork.image_path,
        max_age=3600,
    )


@artworks_bp.route("/artworks/<int:artwork_id>/listing", methods=["GET"])
@login_required
def show_listing_form(artwork_id: int):
    """作者に出品設定画面を表示する。"""
    artwork = artwork_service.get_owned_artwork(artwork_id, current_user)
    if artwork.status != "draft":
        flash("この作品は既に出品済みです。", "error")
        return redirect(url_for("main.home"))
    if not artwork.is_saved:
        flash("画像が保存されていない作品はまだ出品できません。", "error")
        return redirect(url_for("artworks.show_drawing_setup"))

    return render_template(
        "artworks/listing.html",
        artwork=artwork,
        tags=tag_service.list_tags(),
        durations=current_app.config["AUCTION_DURATION_MINUTES"],
        default_minutes=current_app.config["DEFAULT_AUCTION_MINUTES"],
    )


@artworks_bp.route("/artworks/<int:artwork_id>/listing", methods=["POST"])
@login_required
def publish_auction(artwork_id: int):
    """出品情報を受け付けて作品を公開する。"""
    artwork = artwork_service.get_owned_artwork(artwork_id, current_user)
    tag_ids = request.form.getlist("tag_ids")
    try:
        auction = auction_service.create_auction(
            current_user,
            artwork,
            request.form.get("title", ""),
            request.form.get("description", ""),
            tag_ids,
            request.form.get("start_price", 0),
            request.form.get("duration_minutes", current_app.config["DEFAULT_AUCTION_MINUTES"]),
        )
        db.session.commit()
    except ServiceError as error:
        db.session.rollback()
        flash(error.message, "error")
        return redirect(url_for("artworks.show_listing_form", artwork_id=artwork.id))

    flash("出品しました。オークションを開始しました。", "success")
    return redirect(url_for("auctions.show_auction_detail", auction_id=auction.id))


@artworks_bp.route("/artworks/<int:artwork_id>/metadata", methods=["POST"])
@login_required
def update_draft_metadata(artwork_id: int):
    """下書きの出品情報（タイトル・説明）だけを更新する。"""
    artwork = artwork_service.get_owned_artwork(artwork_id, current_user)
    try:
        artwork_service.update_draft_metadata(
            current_user,
            artwork,
            request.form.get("title", ""),
            request.form.get("description", ""),
        )
        db.session.commit()
    except ServiceError as error:
        db.session.rollback()
        flash(error.message, "error")
    else:
        flash("出品情報を更新しました。", "success")
    return redirect(url_for("account.show_account", tab="drafts"))


@artworks_bp.route("/artworks/<int:artwork_id>/download/<kind>")
@login_required
def download_artwork_asset(artwork_id: int, kind: str):
    """原寸 PNG またはレイヤー ZIP を作者・落札者にだけ返す。"""
    artwork = Artwork.query.get(artwork_id)
    if artwork is None:
        flash("作品が見つかりません。", "error")
        return redirect(url_for("main.home"))

    if not _can_download(artwork):
        flash("ダウンロードできる権限がありません。", "error")
        return redirect(url_for("main.home"))

    if kind == "original" and artwork.image_path:
        return send_from_directory(
            upload_root(current_app.config["UPLOAD_FOLDER"]),
            artwork.image_path,
            as_attachment=True,
            download_name=f"hew2026-artwork-{artwork.id}.png",
        )
    if kind == "layers" and artwork.layer_archive_path:
        return send_from_directory(
            upload_root(current_app.config["UPLOAD_FOLDER"]),
            artwork.layer_archive_path,
            as_attachment=True,
            download_name=f"hew2026-artwork-{artwork.id}-layers.zip",
        )

    flash("ダウンロード用のファイルがありません。", "error")
    return redirect(url_for("main.home"))


def _is_owner(artwork) -> bool:
    """ログイン中ユーザーが作者本人かどうかを返す。"""
    from flask_login import current_user

    return current_user.is_authenticated and artwork.artist_id == current_user.id


def _can_download(artwork) -> bool:
    """作者または落札確定済みの落札者だけダウンロードできる。"""
    from flask_login import current_user

    if not current_user.is_authenticated:
        return False
    if artwork.artist_id == current_user.id:
        return True
    auction = artwork.active_auction
    if auction is None:
        return False
    return auction.winner_id is not None and auction.winner_id == current_user.id
