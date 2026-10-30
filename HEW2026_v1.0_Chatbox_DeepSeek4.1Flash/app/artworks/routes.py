"""描画・正式保存・下書き・出品設定・ダウンロード。"""

import os

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required

from ..clock import utcnow
from ..constants import ARTWORK_STATUS_DRAFT
from ..extensions import db
from ..models import Artwork
from ..services import (
    artwork_service,
    auction_service,
    event_service,
    image_service,
    tag_service,
)
from ..services.errors import DomainError

bp = Blueprint("artworks", __name__, url_prefix="/artworks")


def _iso(value):
    """naive UTC の datetime を JavaScript が解釈できる ISO 文字列にする。"""
    return value.isoformat() + "Z" if value else None


def _get_owned_artwork(artwork_id):
    """作品を取得し、作者本人でなければ拒否する。"""
    artwork = artwork_service.get_artwork(artwork_id)
    if artwork is None:
        abort(404)
    if not artwork.is_owned_by(current_user):
        abort(403)
    return artwork


@bp.get("/draw")
@login_required
def show_drawing_setup():
    """描画時間を選ぶ画面。"""
    return render_template(
        "artworks/setup.html",
        durations=current_app.config["DRAWING_DURATIONS"],
        event_closed=event_service.is_event_closed(),
        event_ends_at=event_service.event_ends_at(),
    )


@bp.post("/draw/start")
@login_required
def start_drawing():
    """描画セッションを開始する。開始後は制限時間を変更できない。"""
    try:
        artwork = artwork_service.start_drawing_session(
            current_user, request.form.get("duration_seconds")
        )
    except DomainError as error:
        flash(str(error), "error")
        return redirect(url_for("artworks.show_drawing_setup"))
    return redirect(url_for("artworks.show_canvas", artwork_id=artwork.id))


@bp.get("/<int:artwork_id>/canvas")
@login_required
def show_canvas(artwork_id):
    """描画画面。描画とタイマー表示は JavaScript が担当する。"""
    artwork = _get_owned_artwork(artwork_id)
    if artwork.is_saved:
        flash("正式保存が完了しています。加筆はできません。", "info")
        return redirect(url_for("artworks.show_draft", artwork_id=artwork.id))
    if artwork.save_deadline is None:
        abort(404)

    now = utcnow()
    return render_template(
        "artworks/canvas.html",
        artwork=artwork,
        canvas_size=artwork.canvas_size,
        max_layers=current_app.config["MAX_LAYERS"],
        drawing_deadline_iso=_iso(artwork.drawing_deadline),
        save_deadline_iso=_iso(artwork.save_deadline),
        drawing_seconds_left=max(
            0, int((artwork.drawing_deadline - now).total_seconds())
        ),
        save_seconds_left=max(
            0, int((artwork.save_deadline - now).total_seconds())
        ),
        grace_expired=now > artwork.save_deadline,
        now_iso=_iso(now),
    )


@bp.post("/<int:artwork_id>/save")
@login_required
def save_draft(artwork_id):
    """合成 PNG と全レイヤーデータを受け付け、ZIP を組み立てて保存する。"""
    artwork = _get_owned_artwork(artwork_id)

    composite = request.files.get("composite")
    layer_files = [item.read() for item in request.files.getlist("layers") if item]
    manifest = request.form.get("manifest")

    if composite is None:
        return jsonify(ok=False, error="合成 PNG が送信されていません。"), 400

    try:
        artwork, grant = artwork_service.save_draft_assets(
            artwork,
            composite.read(),
            layer_files,
            manifest,
        )
    except DomainError as error:
        return jsonify(ok=False, error=str(error)), 400

    return jsonify(
        ok=True,
        artwork_id=artwork.id,
        saved_at=format_saved_at(artwork.asset_saved_at),
        bonus=grant.amount if grant else 0,
        redirect=url_for("artworks.show_draft", artwork_id=artwork.id),
    )


def format_saved_at(value):
    from ..clock import format_jst

    return format_jst(value)


@bp.get("/<int:artwork_id>/draft")
@login_required
def show_draft(artwork_id):
    """作者本人に下書きの管理画面を表示する。"""
    artwork = _get_owned_artwork(artwork_id)
    return render_template(
        "artworks/draft.html",
        artwork=artwork,
        auction=artwork.auction,
        can_list=artwork.is_saved and artwork.auction is None,
        grace_expired=(
            artwork.save_deadline is not None
            and not artwork.is_saved
            and utcnow() > artwork.save_deadline
        ),
    )


@bp.post("/<int:artwork_id>/draft")
@login_required
def update_draft(artwork_id):
    """出品情報（タイトル・説明）を更新する。画像の加筆はできない。"""
    artwork = _get_owned_artwork(artwork_id)
    if artwork.auction is not None:
        flash("出品済みの作品は編集できません。", "error")
        return redirect(url_for("artworks.show_draft", artwork_id=artwork.id))
    try:
        artwork_service.update_draft_metadata(
            artwork,
            request.form.get("title"),
            request.form.get("description"),
        )
    except DomainError as error:
        flash(str(error), "error")
    else:
        flash("作品情報を更新しました。", "success")
    return redirect(url_for("artworks.show_draft", artwork_id=artwork.id))


@bp.get("/<int:artwork_id>/listing")
@login_required
def show_listing_form(artwork_id):
    """出品設定画面。タイトル・説明・タグ・開始価格・開催時間を設定する。"""
    artwork = _get_owned_artwork(artwork_id)
    if not artwork.is_saved:
        flash("正式保存が完了していないため出品できません。", "error")
        return redirect(url_for("artworks.show_draft", artwork_id=artwork.id))
    if artwork.auction is not None:
        flash("この作品はすでに出品されています。", "info")
        return redirect(
            url_for("auctions.show_auction_detail", auction_id=artwork.auction.id)
        )
    return render_template(
        "artworks/listing.html",
        artwork=artwork,
        tags=tag_service.list_tags(),
        durations=current_app.config["AUCTION_DURATIONS"],
        default_minutes=current_app.config["DEFAULT_AUCTION_MINUTES"],
        event_ends_at=event_service.event_ends_at(),
    )


@bp.post("/<int:artwork_id>/listing")
@login_required
def publish_auction(artwork_id):
    """出品を確定し、競売を開始する。"""
    artwork = _get_owned_artwork(artwork_id)
    try:
        auction = auction_service.create_auction(
            current_user,
            artwork.id,
            request.form.get("title"),
            request.form.get("description"),
            request.form.get("start_price"),
            request.form.get("duration_minutes"),
            request.form.getlist("tag_ids"),
        )
    except DomainError as error:
        flash(str(error), "error")
        return redirect(url_for("artworks.show_listing_form", artwork_id=artwork.id))

    flash("出品しました。オークションを開始します。", "success")
    return redirect(url_for("auctions.show_auction_detail", auction_id=auction.id))


@bp.get("/<int:artwork_id>/image")
def show_artwork_image(artwork_id):
    """公開用の合成 PNG を返す。下書き・非公開作品は権限を確認する。"""
    artwork = db.session.get(Artwork, artwork_id)
    if artwork is None or not artwork.image_path:
        abort(404)
    if not artwork.is_visible_to(current_user):
        abort(403)
    path = image_service.absolute_path(
        current_app.config["UPLOAD_ROOT"], artwork.image_path
    )
    if not os.path.exists(path):
        abort(404)
    return send_file(path, mimetype="image/png", max_age=0)


@bp.get("/<int:artwork_id>/assets/<kind>")
@login_required
def download_artwork_asset(artwork_id, kind):
    """作者と落札確定済みの落札者だけに原寸 PNG / ZIP を返す。"""
    artwork = db.session.get(Artwork, artwork_id)
    if artwork is None:
        abort(404)

    auction = artwork.auction
    is_winner = bool(
        auction
        and auction.winner_id == current_user.id
        and auction.final_price is not None
    )
    if not (artwork.is_owned_by(current_user) or is_winner or current_user.is_admin()):
        abort(403)

    if kind == "png":
        relative_path = artwork.image_path
        mimetype = "image/png"
        suffix = ".png"
    elif kind == "zip":
        relative_path = artwork.layer_zip_path
        mimetype = "application/zip"
        suffix = ".zip"
    else:
        abort(404)

    if not relative_path:
        abort(404)
    path = image_service.absolute_path(
        current_app.config["UPLOAD_ROOT"], relative_path
    )
    if not os.path.exists(path):
        abort(404)
    return send_file(
        path,
        mimetype=mimetype,
        as_attachment=True,
        download_name=f"hew-artwork-{artwork.id}{suffix}",
        max_age=0,
    )
