from flask import (
    abort, flash, jsonify, redirect, render_template, request, send_file, url_for,
)
from flask_login import current_user, login_required

from app.artworks import bp
from app.constants import AUCTION_DURATIONS_MINUTES, DRAWING_DURATIONS
from app.extensions import db
from app.models import Artwork, Tag
from app.services.artwork_service import (
    create_draft, finish_drawing_session, get_owned_artwork, save_draft_assets,
)
from app.services.auction_service import create_auction, create_relisted_auction
from app.services.common import BusinessError
from app.services.image_service import resolve_upload


@bp.route("/draw", methods=("GET", "POST"))
@login_required
def show_drawing_setup():
    if request.method == "POST":
        try:
            duration = int(request.form.get("duration", "0"))
        except ValueError as exc:
            raise BusinessError("描画時間を選択してください。") from exc
        artwork = create_draft(current_user, duration, request.form.get("title"))
        db.session.commit()
        return redirect(url_for("artworks.show_canvas", artwork_id=artwork.id))
    return render_template("artworks/setup.html", durations=DRAWING_DURATIONS)


@bp.get("/<int:artwork_id>/canvas")
@login_required
def show_canvas(artwork_id):
    artwork = get_owned_artwork(artwork_id, current_user)
    if artwork.is_saved:
        flash("正式保存済みのため加筆できません。出品情報は編集できます。", "info")
        return redirect(url_for("artworks.show_listing_form", artwork_id=artwork.id))
    return render_template("artworks/canvas.html", artwork=artwork, stream=None)


@bp.post("/<int:artwork_id>/finish")
@login_required
def finish_drawing(artwork_id):
    artwork = get_owned_artwork(artwork_id, current_user)
    try:
        finish_drawing_session(artwork)
        db.session.commit()
        return jsonify({"ok": True, "grace_ends_at": artwork.save_grace_ends_at.isoformat() + "Z"})
    except BusinessError as error:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(error)}), 400


@bp.post("/<int:artwork_id>/save")
@login_required
def save_draft(artwork_id):
    artwork = get_owned_artwork(artwork_id, current_user)
    try:
        png = request.files.get("png")
        archive = request.files.get("archive")
        if not png or not archive:
            raise BusinessError("合成PNGとレイヤーZIPの両方を送信してください。")
        artwork, created = save_draft_assets(
            artwork, png.read(), archive.read()
        )
        db.session.commit()
        return jsonify({
            "ok": True, "created": created,
            "listing_url": url_for("artworks.show_listing_form", artwork_id=artwork.id),
        })
    except BusinessError as error:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(error)}), 400


@bp.get("/<int:artwork_id>/image")
def show_artwork_image(artwork_id):
    artwork = db.session.get(Artwork, artwork_id) or abort(404)
    allowed = artwork.is_public or (
        current_user.is_authenticated and current_user.id == artwork.artist_id
    )
    if not allowed or not artwork.image_path:
        abort(404)
    return send_file(resolve_upload(artwork.image_path), mimetype="image/png", max_age=0)


@bp.get("/<int:artwork_id>/download/<asset>")
@login_required
def download_artwork_asset(artwork_id, asset):
    artwork = db.session.get(Artwork, artwork_id) or abort(404)
    is_winner = any(
        a.status == "ended" and a.winner_id == current_user.id
        for a in artwork.auctions
    )
    if current_user.id != artwork.artist_id and not is_winner and not current_user.is_admin:
        abort(403)
    if asset == "png":
        path, mimetype, extension = artwork.image_path, "image/png", "png"
    elif asset == "zip":
        path, mimetype, extension = artwork.archive_path, "application/zip", "zip"
    else:
        abort(404)
    if not path or not artwork.is_saved:
        abort(404)
    return send_file(
        resolve_upload(path), mimetype=mimetype, as_attachment=True,
        download_name=f"{artwork.title}.{extension}",
    )


def _listing_context(artwork):
    return {
        "artwork": artwork,
        "tags": Tag.query.order_by(Tag.name).all(),
        "durations": AUCTION_DURATIONS_MINUTES,
        "is_relist": artwork.status in ("cancelled", "unsold"),
    }


@bp.get("/<int:artwork_id>/listing")
@login_required
def show_listing_form(artwork_id):
    artwork = get_owned_artwork(artwork_id, current_user)
    if artwork.active_auction:
        return redirect(url_for(
            "auctions.show_auction_detail", auction_id=artwork.active_auction.id
        ))
    if artwork.status == "sold":
        raise BusinessError("落札済み作品は再出品できません。")
    return render_template("artworks/listing.html", **_listing_context(artwork))


@bp.post("/<int:artwork_id>/listing")
@login_required
def publish_auction(artwork_id):
    artwork = get_owned_artwork(artwork_id, current_user)
    try:
        start_price = int(request.form.get("start_price", ""))
        duration = int(request.form.get("duration_minutes", ""))
        tag_ids = {int(value) for value in request.form.getlist("tags")}
    except ValueError as exc:
        raise BusinessError("価格・開催時間・タグを正しく入力してください。") from exc
    title = request.form.get("title", "").strip()
    if not 1 <= len(title) <= 200:
        raise BusinessError("タイトルは1〜200文字で入力してください。")
    tags = Tag.query.filter(Tag.id.in_(tag_ids)).all() if tag_ids else []
    if len(tags) != len(tag_ids):
        raise BusinessError("登録済みタグだけを選択してください。")
    artwork.title = title
    artwork.description = request.form.get("description", "").strip()
    artwork.tags = tags
    is_relist = artwork.status in ("cancelled", "unsold")
    factory = create_relisted_auction if is_relist else create_auction
    auction = factory(artwork, start_price, duration)
    db.session.commit()
    flash("オークションを開始しました。非表示レイヤーも落札者へ渡されます。", "success")
    return redirect(url_for("auctions.show_auction_detail", auction_id=auction.id))


@bp.get("/<int:artwork_id>")
def show_artwork(artwork_id):
    artwork = db.session.get(Artwork, artwork_id) or abort(404)
    if artwork.latest_auction:
        return redirect(url_for(
            "auctions.show_auction_detail", auction_id=artwork.latest_auction.id
        ))
    if current_user.is_authenticated and current_user.id == artwork.artist_id:
        return redirect(url_for("artworks.show_listing_form", artwork_id=artwork.id))
    abort(404)
