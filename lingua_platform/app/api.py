"""JSON 接口：课程完成、社区互动与统计数据。"""
from flask import Blueprint, jsonify, request, url_for
from flask_login import current_user, login_required

from . import services
from .extensions import db
from .models import Comment, Course, Lesson, Post, PostLike

bp = Blueprint("api", __name__, url_prefix="/api")

VALID_LANGS = {"all", "en", "ja", "ko"}


@bp.route("/lesson/<int:lesson_id>/complete", methods=["POST"])
@login_required
def complete_lesson(lesson_id):
    lesson = db.session.get(Lesson, lesson_id)
    if not lesson:
        return jsonify({"ok": False, "error": "not_found"}), 404
    if not services.is_course_unlocked(current_user, lesson.course):
        return jsonify({"ok": False, "error": "locked"}), 403

    data = request.get_json(silent=True) or {}
    try:
        score = int(round(float(data.get("score", 0))))
    except (TypeError, ValueError):
        score = 0

    before_stats = services.course_stats(current_user, lesson.course)
    result = services.complete_lesson(current_user, lesson, score)

    next_lesson = None
    for item in lesson.course.lessons:
        if item.order > lesson.order:
            next_lesson = item
            break

    course_stats = services.course_stats(current_user, lesson.course)
    unlocked_next_level = None
    if before_stats["completed"] < before_stats["total"] and course_stats["completed"] == course_stats["total"]:
        for sibling in lesson.course.language.courses:
            if sibling.level == lesson.course.level + 1 and services.is_course_unlocked(
                current_user, sibling
            ):
                unlocked_next_level = {
                    "id": sibling.id,
                    "title": sibling.title,
                    "level_code": sibling.level_code,
                    "url": url_for("main.course", course_id=sibling.id),
                }
                break

    result.update(
        {
            "ok": True,
            "course": {
                "percent": course_stats["percent"],
                "completed": course_stats["completed"],
                "total": course_stats["total"],
            },
            "next_lesson": (
                {
                    "id": next_lesson.id,
                    "title": next_lesson.title,
                    "url": url_for("main.lesson", lesson_id=next_lesson.id),
                }
                if next_lesson
                else None
            ),
            "course_url": url_for("main.course", course_id=lesson.course_id),
            "unlocked_next_level": unlocked_next_level,
        }
    )
    return jsonify(result)


@bp.route("/posts", methods=["POST"])
@login_required
def create_post():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    content = (data.get("content") or "").strip()
    language_code = (data.get("language_code") or "all").strip()

    if language_code not in VALID_LANGS:
        language_code = "all"
    if not 4 <= len(title) <= 140:
        return jsonify({"ok": False, "error": "标题需为 4-140 个字符。"}), 400
    if not 10 <= len(content) <= 2000:
        return jsonify({"ok": False, "error": "正文需为 10-2000 个字符。"}), 400

    post = Post(
        user_id=current_user.id,
        language_code=language_code,
        title=title,
        content=content,
    )
    db.session.add(post)
    db.session.flush()

    newly = services.check_achievements(current_user)
    db.session.commit()

    return jsonify(
        {
            "ok": True,
            "post_id": post.id,
            "url": url_for("main.post_detail", post_id=post.id),
            "achievements": [services.achievement_to_dict(a) for a in newly],
        }
    )


@bp.route("/posts/<int:post_id>/like", methods=["POST"])
@login_required
def toggle_like(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"ok": False, "error": "not_found"}), 404

    like = PostLike.query.filter_by(user_id=current_user.id, post_id=post.id).first()
    if like:
        db.session.delete(like)
        liked = False
    else:
        db.session.add(PostLike(user_id=current_user.id, post_id=post.id))
        liked = True
    db.session.commit()
    return jsonify({"ok": True, "liked": liked, "count": post.like_count})


@bp.route("/posts/<int:post_id>/comments", methods=["POST"])
@login_required
def add_comment(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"ok": False, "error": "not_found"}), 404

    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    if not 1 <= len(content) <= 500:
        return jsonify({"ok": False, "error": "评论需为 1-500 个字符。"}), 400

    comment = Comment(post_id=post.id, user_id=current_user.id, content=content)
    db.session.add(comment)
    db.session.commit()

    return jsonify(
        {
            "ok": True,
            "comment": {
                "id": comment.id,
                "content": comment.content,
                "author": current_user.display_name,
                "initial": current_user.initial,
                "color": current_user.avatar_color,
                "created_at": comment.created_at.strftime("%m月%d日 %H:%M"),
                "count": len(post.comments),
            },
        }
    )


@bp.route("/stats")
@login_required
def stats():
    return jsonify({"ok": True, "stats": services.build_stats(current_user)})
