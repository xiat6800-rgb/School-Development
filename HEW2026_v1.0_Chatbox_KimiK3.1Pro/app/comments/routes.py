from flask import abort, flash, jsonify, redirect, request, url_for
from flask_login import current_user, login_required

from app.comments import bp
from app.extensions import db
from app.models import StreamComment
from app.services.comment_service import create_comment, delete_comment, hide_comment


@bp.post("/streams/<int:stream_id>/comments")
@login_required
def post_comment(stream_id):
    comment = create_comment(stream_id, current_user, request.form.get("body"))
    db.session.commit()
    if request.accept_mimetypes.best == "application/json":
        return jsonify({"ok": True, "id": comment.id}), 201
    flash("コメントを投稿しました。", "success")
    return redirect(url_for("streams.show_stream", stream_id=stream_id))


@bp.post("/comments/<int:comment_id>/delete")
@login_required
def delete_own_comment(comment_id):
    comment = db.session.get(StreamComment, comment_id) or abort(404)
    delete_comment(comment, current_user)
    db.session.commit()
    if request.accept_mimetypes.best == "application/json":
        return jsonify({"ok": True})
    flash("コメントを削除しました。", "success")
    return redirect(url_for("streams.show_stream", stream_id=comment.stream_id))


@bp.post("/comments/<int:comment_id>/hide")
@login_required
def hide_comment_route(comment_id):
    comment = db.session.get(StreamComment, comment_id) or abort(404)
    hide_comment(comment, current_user, request.form.get("reason", ""))
    db.session.commit()
    if request.accept_mimetypes.best == "application/json":
        return jsonify({"ok": True})
    flash("コメントを非表示にしました。", "success")
    return redirect(url_for("streams.show_stream", stream_id=comment.stream_id))
