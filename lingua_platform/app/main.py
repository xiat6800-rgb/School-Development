"""页面路由。"""
from datetime import date, datetime, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from . import services
from .extensions import db
from .models import (
    Achievement,
    Course,
    Language,
    Lesson,
    LessonProgress,
    Post,
    StudyLog,
    User,
    UserAchievement,
)
from .seed_data import LESSON_META

bp = Blueprint("main", __name__)

POST_FILTERS = [("all", "全部"), ("en", "英语"), ("ja", "日语"), ("ko", "韩语")]


@bp.app_context_processor
def inject_globals():
    return {
        "nav_languages": Language.query.order_by(Language.id).all(),
        "post_filters": POST_FILTERS,
        "today": date.today(),
    }


@bp.route("/")
def index():
    languages = Language.query.order_by(Language.id).all()
    stats = {
        "languages": len(languages),
        "courses": Course.query.count(),
        "lessons": Lesson.query.count(),
        "learners": sum(lang.learners for lang in languages),
    }
    featured = Post.query.order_by(Post.created_at.desc()).limit(3).all()
    achievements = Achievement.query.order_by(Achievement.sort).limit(6).all()
    return render_template(
        "index.html",
        languages=languages,
        stats=stats,
        featured=featured,
        achievements=achievements,
    )


@bp.route("/dashboard")
@login_required
def dashboard():
    overview = services.language_overview(current_user)
    recommendations = services.get_recommendations(current_user, limit=4)
    done_ids = services.completed_ids(current_user)
    started_courses = []
    for course in Course.query.all():
        st = services.course_stats(current_user, course, done_ids)
        if 0 < st["completed"] < st["total"]:
            started_courses.append(
                {
                    "course": course,
                    "stats": st,
                    "next": services.next_lesson_for(current_user, course, done_ids),
                }
            )
    started_courses.sort(key=lambda row: row["stats"]["percent"], reverse=True)

    unlocked_rows, unlocked_count = services.achievement_overview(current_user)
    recent_achievements = sorted(
        [row for row in unlocked_rows if row["unlocked"]],
        key=lambda row: row["unlocked_at"] or datetime.min,
        reverse=True,
    )[:4]

    start = date.today() - timedelta(days=6)
    logs = {
        log.day: log
        for log in StudyLog.query.filter(
            StudyLog.user_id == current_user.id, StudyLog.day >= start
        ).all()
    }
    week = []
    for offset in range(7):
        day = start + timedelta(days=offset)
        log = logs.get(day)
        week.append(
            {
                "label": ["一", "二", "三", "四", "五", "六", "日"][day.weekday()],
                "xp": log.xp if log else 0,
                "is_today": day == date.today(),
            }
        )

    today_xp = current_user.today_xp()
    goal = current_user.daily_goal or 30

    return render_template(
        "dashboard.html",
        overview=overview,
        recommendations=recommendations,
        started_courses=started_courses[:2],
        achievements=recent_achievements,
        unlocked_count=unlocked_count,
        achievement_total=Achievement.query.count(),
        week=week,
        today_xp=today_xp,
        goal=goal,
        goal_percent=min(100, round(today_xp / goal * 100)) if goal else 0,
        metrics=services.compute_metrics(current_user),
        kind_meta=LESSON_META,
    )


@bp.route("/languages")
def languages():
    done_ids = services.completed_ids(current_user) if current_user.is_authenticated else set()
    rows = []
    for language in Language.query.order_by(Language.id).all():
        courses = []
        for course in language.courses:
            st = services.course_stats(current_user, course, done_ids)
            courses.append(
                {
                    "course": course,
                    "stats": st,
                    "unlocked": services.is_course_unlocked(
                        current_user, course, done_ids
                    ),
                }
            )
        rows.append({"language": language, "courses": courses})
    return render_template("languages.html", rows=rows)


@bp.route("/course/<int:course_id>")
def course(course_id):
    course = db.session.get(Course, course_id)
    if not course:
        abort(404)
    done_ids = services.completed_ids(current_user) if current_user.is_authenticated else set()
    stats = services.course_stats(current_user, course, done_ids)
    unlocked = services.is_course_unlocked(current_user, course, done_ids)
    progress_map = {}
    if current_user.is_authenticated:
        progress_map = {
            row.lesson_id: row
            for row in LessonProgress.query.filter_by(user_id=current_user.id).all()
        }
    next_lesson = (
        services.next_lesson_for(current_user, course, done_ids)
        if current_user.is_authenticated
        else course.lessons[0]
    )
    siblings = []
    next_course = None
    for sibling in course.language.courses:
        if sibling.level == course.level + 1:
            next_course = sibling
        sibling_stats = services.course_stats(current_user, sibling, done_ids)
        siblings.append(
            {
                "course": sibling,
                "stats": sibling_stats,
                "unlocked": services.is_course_unlocked(current_user, sibling, done_ids),
            }
        )
    return render_template(
        "course.html",
        course=course,
        stats=stats,
        unlocked=unlocked,
        progress_map=progress_map,
        next_lesson=next_lesson,
        siblings=siblings,
        next_course=next_course,
        kind_meta=LESSON_META,
    )


@bp.route("/lesson/<int:lesson_id>")
@login_required
def lesson(lesson_id):
    lesson = db.session.get(Lesson, lesson_id)
    if not lesson:
        abort(404)
    course = lesson.course
    if not services.is_course_unlocked(current_user, course):
        flash("请先完成上一级别的全部课程，才能解锁本课。", "info")
        return redirect(url_for("main.course", course_id=course.id))

    payload = services.lesson_payload(lesson)
    progress = LessonProgress.query.filter_by(
        user_id=current_user.id, lesson_id=lesson.id
    ).first()
    next_lesson = None
    for item in course.lessons:
        if item.order > lesson.order:
            next_lesson = item
            break
    return render_template(
        "lesson.html",
        lesson=lesson,
        course=course,
        payload=payload,
        progress=progress,
        next_lesson=next_lesson,
    )


@bp.route("/progress")
@login_required
def progress():
    overview = services.language_overview(current_user)
    rows, unlocked_count = services.achievement_overview(current_user)
    return render_template(
        "progress.html",
        overview=overview,
        unlocked_count=unlocked_count,
        achievement_total=len(rows),
    )


@bp.route("/achievements")
@login_required
def achievements():
    rows, unlocked_count = services.achievement_overview(current_user)
    return render_template(
        "achievements.html",
        rows=rows,
        unlocked_count=unlocked_count,
        total=len(rows),
    )


@bp.route("/community")
def community():
    code = request.args.get("lang", "all")
    if code not in {key for key, _ in POST_FILTERS}:
        code = "all"
    query = Post.query
    if code != "all":
        query = query.filter_by(language_code=code)
    posts = query.order_by(Post.created_at.desc()).all()
    liked_ids = set()
    if current_user.is_authenticated:
        liked_ids = {like.post_id for like in current_user.likes}
    leaderboard = (
        User.query.order_by(User.total_xp.desc(), User.streak.desc()).limit(5).all()
    )
    counts = {key: Post.query.filter_by(language_code=key).count() for key, _ in POST_FILTERS}
    counts["all"] = Post.query.count()
    return render_template(
        "community.html",
        posts=posts,
        active_filter=code,
        liked_ids=liked_ids,
        leaderboard=leaderboard,
        counts=counts,
    )


@bp.route("/community/<int:post_id>")
def post_detail(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        abort(404)
    liked = False
    if current_user.is_authenticated:
        liked = any(like.user_id == current_user.id for like in post.likes)
    related = (
        Post.query.filter(Post.id != post.id)
        .order_by(Post.created_at.desc())
        .limit(3)
        .all()
    )
    return render_template(
        "post_detail.html", post=post, liked=liked, related=related
    )


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        display_name = (request.form.get("display_name") or "").strip()
        bio = (request.form.get("bio") or "").strip()
        goal_raw = request.form.get("daily_goal") or "30"
        try:
            goal = max(10, min(200, int(goal_raw)))
        except ValueError:
            goal = 30

        if not 1 <= len(display_name) <= 20:
            flash("昵称需为 1-20 个字符。", "error")
            return redirect(url_for("main.profile"))

        current_user.display_name = display_name
        current_user.bio = bio[:200]
        current_user.daily_goal = goal
        db.session.commit()
        flash("个人资料已更新。", "success")
        return redirect(url_for("main.profile"))

    stats = services.build_stats(current_user)
    rows, unlocked_count = services.achievement_overview(current_user)
    unlocked = [row for row in rows if row["unlocked"]][:6]
    return render_template(
        "profile.html",
        stats=stats,
        unlocked=unlocked,
        unlocked_count=unlocked_count,
        total=len(rows),
    )
