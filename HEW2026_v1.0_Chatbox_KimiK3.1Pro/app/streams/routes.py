from flask import (
    abort, flash, jsonify, redirect, render_template, request, send_file, url_for,
)
from flask_login import current_user, login_required

from app.constants import DRAWING_DURATIONS
from app.extensions import db
from app.models import LiveStream
from app.services.artwork_service import create_draft
from app.services.comment_service import list_public_comments
from app.services.common import BusinessError
from app.services.image_service import resolve_upload
from app.services.stream_service import (
    close_stale_streams, create_stream, end_stream, heartbeat_stream, pause_stream,
    resume_stream, start_stream, update_stream_preview,
)
from app.streams import bp


def _stream_or_404(stream_id):
    return db.session.get(LiveStream, stream_id) or abort(404)


def _owned_stream(stream_id):
    stream = _stream_or_404(stream_id)
    if not current_user.is_authenticated or stream.artwork.artist_id != current_user.id:
        abort(403)
    return stream


@bp.route("/prepare", methods=("GET", "POST"))
@login_required
def prepare_stream():
    if request.method == "POST":
        try:
            duration = int(request.form.get("duration", "0"))
        except ValueError as exc:
            raise BusinessError("描画時間を選択してください。") from exc
        artwork = create_draft(current_user, duration, request.form.get("title"))
        stream = create_stream(artwork)
        db.session.commit()
        return redirect(url_for("streams.show_studio", stream_id=stream.id))
    return render_template("streams/prepare.html", durations=DRAWING_DURATIONS)


@bp.get("/<int:stream_id>/studio")
@login_required
def show_studio(stream_id):
    stream = _owned_stream(stream_id)
    if stream.artwork.is_saved:
        return redirect(url_for("artworks.show_listing_form", artwork_id=stream.artwork_id))
    return render_template(
        "artworks/canvas.html", artwork=stream.artwork, stream=stream
    )


@bp.get("/<int:stream_id>")
def show_stream(stream_id):
    close_stale_streams()
    db.session.commit()
    stream = _stream_or_404(stream_id)
    hidden_by_admin = not stream.artwork.is_public and stream.artwork.visibility_reason
    if hidden_by_admin and not (
        current_user.is_authenticated
        and (current_user.id == stream.artwork.artist_id or current_user.is_admin)
    ):
        abort(404)
    return render_template(
        "streams/show.html", stream=stream, comments=list_public_comments(stream)
    )


@bp.post("/<int:stream_id>/start")
@login_required
def start_stream_route(stream_id):
    stream = _owned_stream(stream_id)
    start_stream(stream, current_user)
    db.session.commit()
    flash("制作配信を開始しました。コメントを受け付けます。", "success")
    return redirect(url_for("streams.show_studio", stream_id=stream.id))


@bp.post("/<int:stream_id>/pause")
@login_required
def pause_stream_route(stream_id):
    stream = _owned_stream(stream_id)
    pause_stream(stream, current_user)
    db.session.commit()
    return jsonify({"ok": True, "status": stream.status})


@bp.post("/<int:stream_id>/resume")
@login_required
def resume_stream_route(stream_id):
    stream = _owned_stream(stream_id)
    resume_stream(stream, current_user)
    db.session.commit()
    return jsonify({"ok": True, "status": stream.status})


@bp.post("/<int:stream_id>/end")
@login_required
def end_stream_route(stream_id):
    stream = _owned_stream(stream_id)
    end_stream(stream, current_user)
    db.session.commit()
    flash("配信を終了しました。この作品では再配信できません。", "success")
    return redirect(url_for("streams.show_studio", stream_id=stream.id))


@bp.post("/<int:stream_id>/heartbeat")
@login_required
def heartbeat(stream_id):
    stream = _owned_stream(stream_id)
    try:
        heartbeat_stream(stream, current_user)
        db.session.commit()
        return jsonify({"ok": True, "status": stream.status})
    except BusinessError as error:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(error)}), 400


@bp.post("/<int:stream_id>/preview")
@login_required
def upload_preview(stream_id):
    stream = _owned_stream(stream_id)
    try:
        file = request.files.get("preview")
        if not file:
            raise BusinessError("プレビュー画像がありません。")
        update_stream_preview(stream, current_user, file.read())
        db.session.commit()
        return jsonify({"ok": True})
    except BusinessError as error:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(error)}), 400


@bp.get("/<int:stream_id>/preview")
def show_preview(stream_id):
    stream = _stream_or_404(stream_id)
    if not stream.preview_path:
        abort(404)
    return send_file(resolve_upload(stream.preview_path), mimetype="image/png", max_age=0)


@bp.get("/<int:stream_id>/state")
def stream_state(stream_id):
    stream = _stream_or_404(stream_id)
    comments = list_public_comments(stream)
    return jsonify({
        "status": stream.status,
        "end_reason": stream.end_reason,
        "preview_version": stream.updated_at.isoformat() + "Z",
        "comments": [{
            "id": c.id,
            "user": c.user.display_name if c.status == "visible" else "",
            "body": c.body if c.status == "visible" else None,
            "status": c.status,
            "delete_url": (
                url_for("comments.delete_own_comment", comment_id=c.id)
                if current_user.is_authenticated and c.status == "visible"
                and c.user_id == current_user.id else None
            ),
            "hide_url": (
                url_for("comments.hide_comment_route", comment_id=c.id)
                if current_user.is_authenticated and c.status == "visible"
                and c.user_id != current_user.id
                and (current_user.id == stream.artwork.artist_id or current_user.is_admin)
                else None
            ),
            "created_at": c.created_at.isoformat() + "Z",
        } for c in comments],
    })
