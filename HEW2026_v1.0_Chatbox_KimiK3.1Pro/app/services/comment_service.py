import calendar
from datetime import datetime, timedelta, timezone

from flask import current_app

from app.constants import COMMENT_INTERVAL_SECONDS, COMMENT_MAX_LENGTH
from app.extensions import db
from app.models import CommentAudit, LiveStream, StreamComment
from app.services.common import BusinessError
from app.utils import JST, utcnow


def create_comment(stream_id, user, body, *, now=None):
    now = now or utcnow()
    stream = LiveStream.query.filter_by(id=stream_id).with_for_update().first()
    if not stream:
        raise BusinessError("配信が見つかりません。")
    body = (body or "").strip()
    if not body:
        raise BusinessError("空白だけのコメントは投稿できません。")
    if len(body) > COMMENT_MAX_LENGTH:
        raise BusinessError("コメントは200文字以内で入力してください。")
    if (
        stream.status != "live"
        or now >= stream.artwork.drawing_ends_at
        or now >= current_app.config["EVENT_ENDS_AT"]
    ):
        raise BusinessError("コメントは配信中だけ投稿できます。")
    latest = StreamComment.query.filter_by(
        stream_id=stream.id, user_id=user.id
    ).order_by(StreamComment.id.desc()).first()
    if latest and (now - latest.created_at).total_seconds() < COMMENT_INTERVAL_SECONDS:
        raise BusinessError("同じユーザーは3秒に1件まで投稿できます。")
    comment = StreamComment(stream=stream, user=user, body=body)
    db.session.add(comment)
    db.session.flush()
    return comment


def list_public_comments(stream):
    # 非表示本文は返さず、監査対象のIDと状態だけを履歴に残す。
    return StreamComment.query.filter_by(stream_id=stream.id).order_by(
        StreamComment.id
    ).all()


def calculate_body_purge_at(moderated_at):
    if moderated_at.tzinfo is None:
        moderated_at = moderated_at.replace(tzinfo=timezone.utc)
    local = moderated_at.astimezone(JST)
    year = local.year + (1 if local.month == 12 else 0)
    month = 1 if local.month == 12 else local.month + 1
    day = min(local.day, calendar.monthrange(year, month)[1])
    purge_local = local.replace(year=year, month=month, day=day)
    return purge_local.astimezone(timezone.utc).replace(tzinfo=None)


def _moderate_comment(comment, operator, action, reason="", *, now=None):
    now = now or utcnow()
    if comment.status != "visible":
        return comment
    comment.status = "deleted" if action == "delete" else "hidden"
    comment.moderated_at = now
    comment.purge_body_at = calculate_body_purge_at(now)
    db.session.add(CommentAudit(
        comment=comment, operator=operator, action=action,
        reason=(reason or "").strip(),
    ))
    db.session.flush()
    return comment


def delete_comment(comment, operator, *, now=None):
    if comment.user_id != operator.id:
        raise BusinessError("自分のコメントだけを削除できます。")
    return _moderate_comment(comment, operator, "delete", now=now)


def hide_comment(comment, operator, reason="", *, now=None):
    if operator.id != comment.stream.artwork.artist_id and not operator.is_admin:
        raise BusinessError("配信者・管理者だけがコメントを非表示にできます。")
    return _moderate_comment(comment, operator, "hide", reason, now=now)


def purge_expired_comment_bodies(*, now=None):
    now = now or utcnow()
    comments = StreamComment.query.filter(
        StreamComment.status != "visible",
        StreamComment.purge_body_at <= now,
        StreamComment.purged_at.is_(None),
    ).all()
    for comment in comments:
        comment.body = None
        comment.purged_at = now
    db.session.flush()
    return len(comments)


def get_comment_audit():
    return CommentAudit.query.order_by(CommentAudit.id.desc()).all()


def admin_visible_body(comment, *, now=None):
    now = now or utcnow()
    if comment.purged_at or (comment.purge_body_at and now >= comment.purge_body_at):
        return None
    return comment.body
