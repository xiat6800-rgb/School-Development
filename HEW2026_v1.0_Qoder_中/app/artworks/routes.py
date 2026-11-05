"""描画・下書き・出品設定のルート。"""
import base64
from pathlib import Path

from flask import (
    abort,
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

from ..extensions import db
from ..models.artwork import Artwork
from ..services import (
    artwork_service,
    auction_service,
    event_service,
    image_service,
    layer_service,
    tag_service,
)
from ..services.artwork_service import ArtworkError
from ..services.event_service import EventClosedError
from . import bp


def _get_owned_artwork(artwork_id):
    artwork = db.session.get(Artwork, artwork_id)
    if artwork is None:
        abort(404)
    if artwork.artist_id != current_user.id:
        abort(403)
    return artwork


@bp.route("/draw/setup")
@login_required
def show_drawing_setup():
    """10秒・30秒・1分・5分から描画時間を選択する画面を表示する。"""
    try:
        event_service.validate_event_operation("描画開始")
    except EventClosedError as exc:
        flash(str(exc), "error")
        return redirect(url_for("main.show_top"))
    return render_template(
        "artworks/draw_setup.html",
        durations=current_app.config["ALLOWED_DRAWING_DURATIONS"],
    )


@bp.route("/draw/start", methods=["POST"])
@login_required
def start_drawing():
    """下書きを作成し、サーバー管理の開始時刻・期限を記録して描画画面へ進む。"""
    try:
        duration = int(request.form.get("duration_seconds", 0))
    except ValueError:
        duration = 0
    try:
        artwork = artwork_service.create_draft(current_user)
        artwork_service.start_drawing_session(artwork, duration)
    except (ArtworkError, EventClosedError) as exc:
        flash(str(exc), "error")
        return redirect(url_for("artworks.show_drawing_setup"))
    return redirect(url_for("artworks.show_canvas", artwork_id=artwork.id))


@bp.route("/draw/<int:artwork_id>")
@login_required
def show_canvas(artwork_id):
    """描画画面を表示する。描画とタイマー表示は JavaScript が担当する。"""
    artwork = _get_owned_artwork(artwork_id)
    if artwork.drawing_started_at is None:
        flash("描画セッションが開始されていません。", "error")
        return redirect(url_for("artworks.show_drawing_setup"))
    return render_template(
        "artworks/draw.html",
        artwork=artwork,
        deadline_utc=artwork.drawing_deadline.isoformat() + "Z",
        max_layers=current_app.config["MAX_LAYERS"],
        canvas_size=current_app.config["CANVAS_SIZE"],
    )


@bp.route("/<int:artwork_id>/save", methods=["POST"])
@login_required
def save_draft(artwork_id):
    """完成・時間切れ時の合成PNGと全レイヤーデータを受け付ける。"""
    artwork = _get_owned_artwork(artwork_id)
    png_bytes = _read_upload("composite_png")
    zip_bytes = _read_upload("layers_zip")
    if png_bytes is None or zip_bytes is None:
        return jsonify(ok=False, error="合成PNGとレイヤーZIPの両方が必要です。"), 400
    try:
        artwork_service.save_draft_assets(artwork, png_bytes, zip_bytes)
    except (
        ArtworkError,
        image_service.InvalidImageError,
        layer_service.InvalidLayerArchiveError,
    ) as exc:
        return jsonify(ok=False, error=str(exc)), 400
    return jsonify(ok=True, listing_url=url_for("artworks.show_listing_form", artwork_id=artwork.id))


def _read_upload(field):
    """multipart ファイル、または JSON 内の base64 データを読み取る。"""
    file = request.files.get(field)
    if file is not None:
        return file.read()
    data = (request.get_json(silent=True) or {}).get(field)
    if data:
        try:
            return base64.b64decode(data)
        except Exception:
            return None
    return None


@bp.route("/draft/<int:artwork_id>")
@login_required
def show_draft(artwork_id):
    """作者本人に下書きの管理画面を表示する。"""
    artwork = _get_owned_artwork(artwork_id)
    return render_template("artworks/draft.html", artwork=artwork)


@bp.route("/<int:artwork_id>/listing", methods=["GET"])
@login_required
def show_listing_form(artwork_id):
    """作者に下書きの出品設定画面を表示する。"""
    artwork = _get_owned_artwork(artwork_id)
    if not artwork.is_saved:
        flash("正式保存が完了してから出品設定に進めます。", "error")
        return redirect(url_for("artworks.show_draft", artwork_id=artwork.id))
    if artwork.status != "draft":
        flash("この作品は出品済みです。", "error")
        return redirect(url_for("artworks.show_draft", artwork_id=artwork.id))
    return render_template(
        "artworks/listing.html",
        artwork=artwork,
        tags=tag_service.list_tags(),
        minutes=current_app.config["ALLOWED_AUCTION_MINUTES"],
        default_minutes=current_app.config["DEFAULT_AUCTION_MINUTES"],
    )


@bp.route("/<int:artwork_id>/listing", methods=["POST"])
@login_required
def publish_auction(artwork_id):
    """出品情報を受け付け、サービスへ出品を依頼する。"""
    artwork = _get_owned_artwork(artwork_id)
    tag_ids = [
        int(value)
        for value in request.form.getlist("tag_ids")
        if str(value).isdigit()
    ]
    try:
        start_price = int(request.form.get("start_price", -1))
        duration = int(request.form.get("duration_minutes", 0))
    except ValueError:
        start_price, duration = -1, 0
    try:
        auction = auction_service.create_auction(
            artwork,
            current_user,
            request.form.get("title") or artwork.title,
            request.form.get("description") or "",
            tag_ids,
            start_price,
            duration,
        )
    except (auction_service.AuctionError, EventClosedError) as exc:
        flash(str(exc), "error")
        return redirect(url_for("artworks.show_listing_form", artwork_id=artwork.id))
    flash("出品しました。オークションを開始しました。", "info")
    return redirect(url_for("auctions.show_auction_detail", auction_id=auction.id))


@bp.route("/<int:artwork_id>/image")
def show_public_image(artwork_id):
    """公開用画像の配信。下書きは作者だけに表示する。"""
    artwork = db.session.get(Artwork, artwork_id)
    if artwork is None or not artwork.image_path:
        abort(404)
    if not artwork.is_public:
        if not current_user.is_authenticated or artwork.artist_id != current_user.id:
            abort(403)
    return send_from_directory(
        Path(current_app.config["UPLOAD_FOLDER"]).resolve(), artwork.image_path
    )


@bp.route("/<int:artwork_id>/download/<kind>")
@login_required
def download_artwork_asset(artwork_id, kind):
    """作者・落札確定済みの落札者だけへ原寸PNGまたはZIPを返す。"""
    artwork = db.session.get(Artwork, artwork_id)
    if artwork is None:
        abort(404)
    if kind not in ("png", "zip"):
        abort(404)
    if not artwork_service.can_download_asset(current_user, artwork):
        abort(403)
    filename = artwork.image_path if kind == "png" else artwork.layer_zip_path
    if not filename:
        abort(404)
    suffix = "png" if kind == "png" else "zip"
    return send_from_directory(
        Path(current_app.config["UPLOAD_FOLDER"]).resolve(),
        filename,
        as_attachment=True,
        download_name=f"artwork_{artwork.id}.{suffix}",
    )
