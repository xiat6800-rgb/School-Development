"""アプリ内通知の一覧と既読管理。"""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..services import notification_service

bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@bp.get("/")
@login_required
def index():
    """本人の通知一覧。関連する商品詳細へ移動できる。"""
    return render_template(
        "notifications/index.html",
        notifications=notification_service.list_user_notifications(
            current_user.id, limit=100
        ),
    )


@bp.post("/<int:notification_id>/read")
@login_required
def mark_notification_read(notification_id):
    """所有者を確認して既読にする。"""
    if notification_service.mark_notification_read(
        notification_id, current_user.id
    ):
        next_url = request.form.get("next") or ""
        if next_url.startswith("/") and not next_url.startswith("//"):
            return redirect(next_url)
    return redirect(url_for("notifications.index"))


@bp.post("/read-all")
@login_required
def mark_all_read():
    """未読をまとめて既読にする。"""
    count = notification_service.mark_all_read(current_user.id)
    flash(f"{count}件の通知を既読にしました。", "success")
    return redirect(url_for("notifications.index"))
