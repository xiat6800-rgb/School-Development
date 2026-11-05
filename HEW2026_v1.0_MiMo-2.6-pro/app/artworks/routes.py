import json
import os

from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template,
    request, send_from_directory, url_for,
)
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Artwork
from app.services import artwork_service, auction_service, tag_service
from app.services.artwork_service import DrawingError
from app.services.event_service import EventClosedError

bp = Blueprint("artworks", __name__)

DURATION_CHOICES = (
    (10, "10秒"),
    (30, "30秒"),
    (60, "1分"),
    (300, "5分"),
)


@bp.route("/draw", methods=["GET"])
@login_required
def show_drawing_setup():
    return render_template(
        "artworks/drawing_setup.html", duration_choices=DURATION_CHOICES
    )


@bp.route("/draw/start", methods=["POST"])
@login_required
def start_drawing():
    duration = request.form.get("duration_seconds", type=int)
    try:
        artwork = artwork_service.create_draft(current_user, duration)
    except EventClosedError:
        flash("イベントは終了したため描画を開始できません。", "error")
        return redirect(url_for("artworks.show_drawing_setup"))
    except DrawingError as exc:
        flash(str(exc), "error")
        return redirect(url_for("artworks.show_drawing_setup"))
    return redirect(url_for("artworks.show_canvas", artwork_id=artwork.id))


@bp.route("/draw/<int:artwork_id>", methods=["GET"])
@login_required
def show_canvas(artwork_id):
    artwork = artwork_service.get_artwork_for_owner(artwork_id, current_user)
    if artwork is None:
        abort(404)
    if artwork.is_formally_saved:
        return redirect(url_for("artworks.show_draft", artwork_id=artwork.id))
    deadline_iso = None
    if artwork.drawing_deadline is not None:
        deadline_iso = artwork.drawing_deadline.isoformat() + "Z"
    return render_template(
        "artworks/canvas.html",
        artwork=artwork,
        deadline_iso=deadline_iso,
        canvas_size=current_app.config["CANVAS_SIZE"],
        max_layers=current_app.config["MAX_LAYERS"],
        max_undo=current_app.config["MAX_UNDO"],
        save_grace=current_app.config["SAVE_GRACE_SECONDS"],
    )


@bp.route("/draw/<int:artwork_id>/save", methods=["POST"])
@login_required
def save_draft(artwork_id):
    artwork = artwork_service.get_artwork_for_owner(artwork_id, current_user)
    if artwork is None:
        abort(404)
    if artwork.is_formally_saved:
        return {"status": "ok", "already_saved": True, "artwork_id": artwork.id}

    image_file = request.files.get("image")
    layer_files = request.files.getlist("layers")
    manifest_raw = request.form.get("manifest")
    try:
        manifest = json.loads(manifest_raw) if manifest_raw else None
    except json.JSONDecodeError:
        manifest = None

    try:
        artwork, granted = artwork_service.save_draft_assets(
            artwork, image_file, layer_files, manifest
        )
    except DrawingError as exc:
        return {"status": "error", "message": str(exc)}, 400
    except Exception as exc:  # 検証例外を画面向けに集約
        return {"status": "error", "message": str(exc)}, 400

    return {
        "status": "ok",
        "artwork_id": artwork.id,
        "bonus_granted": granted,
    }


@bp.route("/artworks/<int:artwork_id>", methods=["GET"])
@login_required
def show_draft(artwork_id):
    artwork = artwork_service.get_artwork_for_owner(artwork_id, current_user)
    if artwork is None:
        abort(404)
    return render_template(
        "artworks/draft.html", artwork=artwork, tags=tag_service.list_artwork_tag_names(artwork)
    )


@bp.route("/artworks/<int:artwork_id>/metadata", methods=["POST"])
@login_required
def update_metadata(artwork_id):
    artwork = artwork_service.get_artwork_for_owner(artwork_id, current_user)
    if artwork is None:
        abort(404)
    try:
        artwork_service.update_draft_metadata(
            artwork,
            title=request.form.get("title"),
            description=request.form.get("description"),
        )
        flash("出品情報を更新しました。", "success")
    except DrawingError as exc:
        flash(str(exc), "error")
    return redirect(url_for("artworks.show_draft", artwork_id=artwork.id))


@bp.route("/artworks/<int:artwork_id>/listing", methods=["GET", "POST"])
@login_required
def listing_form(artwork_id):
    artwork = artwork_service.get_artwork_for_owner(artwork_id, current_user)
    if artwork is None:
        abort(404)
    if not artwork.is_formally_saved:
        flash("正式保存が完了していない作品は出品できません。", "error")
        return redirect(url_for("artworks.show_draft", artwork_id=artwork.id))
    if artwork.status != Artwork.STATUS_DRAFT:
        flash("この作品はすでに出品済みです。", "error")
        return redirect(url_for("artworks.show_draft", artwork_id=artwork.id))

    if request.method == "POST":
        tag_ids = request.form.getlist("tag_ids", type=int)
        start_price = request.form.get("start_price", type=int)
        duration = request.form.get(
            "duration_minutes", type=int,
            default=auction_service.DEFAULT_LISTING_DURATION,
        )
        try:
            auction = auction_service.create_auction(
                artwork,
                current_user,
                title=request.form.get("title"),
                description=request.form.get("description"),
                tag_ids=tag_ids,
                start_price=start_price,
                duration_minutes=duration,
            )
        except (auction_service.AuctionError, EventClosedError) as exc:
            flash(str(exc), "error")
            return render_template(
                "artworks/listing_form.html",
                artwork=artwork,
                tags=tag_service.list_tags(),
                durations=auction_service.LISTING_DURATIONS,
                selected_tag_ids=tag_ids,
            )
        flash("出品しました。オークションを開始します。", "success")
        return redirect(url_for("auctions.show_auction_detail", auction_id=auction.id))

    return render_template(
        "artworks/listing_form.html",
        artwork=artwork,
        tags=tag_service.list_tags(),
        durations=auction_service.LISTING_DURATIONS,
        selected_tag_ids=[],
    )


@bp.route("/artworks/<int:artwork_id>/image", methods=["GET"])
def artwork_image(artwork_id):
    """公開用画像の表示。公開作品と作者・落札者のみ参照できる。"""
    artwork = db.session.get(Artwork, artwork_id)
    if artwork is None or not artwork.image_path:
        abort(404)
    is_owner = current_user.is_authenticated and artwork.artist_id == current_user.id
    if not artwork.is_public and not is_owner:
        abort(404)
    directory = os.path.join(
        current_app.config["UPLOAD_FOLDER"], os.path.dirname(artwork.image_path)
    )
    return send_from_directory(directory, os.path.basename(artwork.image_path))


@bp.route("/artworks/<int:artwork_id>/download/<asset>", methods=["GET"])
@login_required
def download_artwork_asset(artwork_id, asset):
    """原寸PNG・レイヤーZIPのダウンロード（作者と落札者のみ）。"""
    artwork = db.session.get(Artwork, artwork_id)
    if artwork is None:
        abort(404)
    if not auction_service.can_download_artwork(current_user, artwork):
        abort(403)
    if asset == "png":
        rel_path = artwork.image_path
    elif asset == "layers":
        rel_path = artwork.layers_zip_path
    else:
        abort(404)
    if not rel_path:
        abort(404)
    directory = os.path.join(
        current_app.config["UPLOAD_FOLDER"], os.path.dirname(rel_path)
    )
    filename = os.path.basename(rel_path)
    download_name = f"artwork_{artwork.id}_{asset}.{'png' if asset == 'png' else 'zip'}"
    return send_from_directory(
        directory, filename, as_attachment=True, download_name=download_name
    )
