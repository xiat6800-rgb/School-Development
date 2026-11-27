"""业务服务：进度、推荐、经验值、成就与课程载荷。"""
from datetime import date, datetime, timedelta

from .extensions import db
from .models import (
    Achievement,
    Course,
    GrammarItem,
    Language,
    Lesson,
    LessonProgress,
    Post,
    SpeakingItem,
    StudyLog,
    UserAchievement,
    VocabItem,
)

KIND_LABELS = {
    "vocab": "单词记忆",
    "grammar": "语法练习",
    "listening": "听力训练",
    "speaking": "口语跟读",
}
KIND_ICONS = {
    "vocab": "📖",
    "grammar": "🧩",
    "listening": "🎧",
    "speaking": "🎙️",
}


# ---------------------------------------------------------------- 进度
def completed_ids(user):
    rows = LessonProgress.query.filter_by(user_id=user.id, completed=True).all()
    return {row.lesson_id for row in rows}


def course_stats(user, course, done_ids=None):
    done_ids = done_ids if done_ids is not None else completed_ids(user)
    total = len(course.lessons)
    done = sum(1 for lesson in course.lessons if lesson.id in done_ids)
    return {
        "total": total,
        "completed": done,
        "percent": round(done / total * 100) if total else 0,
    }


def is_course_unlocked(user, course, done_ids=None):
    if course.level <= 1:
        return True
    done_ids = done_ids if done_ids is not None else completed_ids(user)
    for prev in Course.query.filter_by(
        language_id=course.language_id, level=course.level - 1
    ).all():
        if any(lesson.id not in done_ids for lesson in prev.lessons):
            return False
    return True


def next_lesson_for(user, course, done_ids=None):
    done_ids = done_ids if done_ids is not None else completed_ids(user)
    for lesson in course.lessons:
        if lesson.id not in done_ids:
            return lesson
    return None


def language_overview(user):
    done_ids = completed_ids(user)
    result = []
    for lang in Language.query.order_by(Language.id).all():
        courses = lang.courses
        total = sum(len(c.lessons) for c in courses)
        done = sum(
            1
            for c in courses
            for lesson in c.lessons
            if lesson.id in done_ids
        )
        result.append(
            {
                "language": lang,
                "total": total,
                "completed": done,
                "percent": round(done / total * 100) if total else 0,
            }
        )
    return result


# ---------------------------------------------------------------- 经验值
def _today_log(user, create=True):
    log = StudyLog.query.filter_by(user_id=user.id, day=date.today()).first()
    if not log and create:
        log = StudyLog(user_id=user.id, day=date.today(), xp=0, minutes=0, lessons=0)
        db.session.add(log)
        db.session.flush()
    return log


def _award_xp(user, amount, minutes=0, lessons=0):
    if amount:
        user.total_xp = (user.total_xp or 0) + amount
    log = _today_log(user)
    log.xp += amount
    log.minutes += minutes
    log.lessons += lessons


def _touch_streak(user):
    today = date.today()
    if user.last_study_date == today:
        return
    if user.last_study_date == today - timedelta(days=1):
        user.streak = (user.streak or 0) + 1
    else:
        user.streak = 1
    user.last_study_date = today


# ---------------------------------------------------------------- 完成课程
def complete_lesson(user, lesson, score):
    score = max(0, min(100, int(score)))
    progress = LessonProgress.query.filter_by(
        user_id=user.id, lesson_id=lesson.id
    ).first()
    first_time = progress is None or not progress.completed
    if progress is None:
        progress = LessonProgress(user_id=user.id, lesson_id=lesson.id, best_score=0)
        db.session.add(progress)

    progress.attempts = (progress.attempts or 0) + 1
    progress.best_score = max(progress.best_score or 0, score)
    progress.completed = True
    progress.completed_at = progress.completed_at or datetime.now()
    progress.updated_at = datetime.now()

    if first_time:
        xp = lesson.xp_reward + (10 if score >= 95 else 0)
        minutes = lesson.duration
        lessons_delta = 1
    else:
        xp = max(5, round(lesson.xp_reward * 0.2))
        minutes = 2
        lessons_delta = 0

    _touch_streak(user)
    _award_xp(user, xp, minutes=minutes, lessons=lessons_delta)

    old_level = user.level
    newly = check_achievements(user)
    db.session.commit()

    return {
        "xp": xp,
        "score": score,
        "first_time": first_time,
        "streak": user.streak,
        "total_xp": user.total_xp,
        "level": user.level,
        "level_up": user.level > old_level,
        "achievements": [achievement_to_dict(a) for a in newly],
        "best_score": progress.best_score,
        "next_lesson_url": None,
    }


# ---------------------------------------------------------------- 成就
def achievement_to_dict(achievement):
    return {
        "code": achievement.code,
        "name": achievement.name,
        "description": achievement.description,
        "icon": achievement.icon,
        "xp_reward": achievement.xp_reward,
    }


def compute_metrics(user):
    completed = LessonProgress.query.filter_by(user_id=user.id, completed=True).all()
    lesson_ids = [row.lesson_id for row in completed]
    lessons = []
    if lesson_ids:
        lessons = Lesson.query.filter(Lesson.id.in_(lesson_ids)).all()

    vocab_course_ids = {l.course_id for l in lessons if l.kind == "vocab"}
    words = 0
    for course_id in vocab_course_ids:
        course = db.session.get(Course, course_id)
        if course:
            words += len(course.words)

    language_ids = set()
    for lesson in lessons:
        course = db.session.get(Course, lesson.course_id)
        if course:
            language_ids.add(course.language_id)

    return {
        "xp": user.total_xp or 0,
        "streak": user.streak or 0,
        "lessons": len(completed),
        "words": words,
        "speaking": sum(1 for l in lessons if l.kind == "speaking"),
        "posts": Post.query.filter_by(user_id=user.id).count(),
        "languages": len(language_ids),
        "perfect": sum(1 for row in completed if (row.best_score or 0) >= 100),
    }


def check_achievements(user):
    unlocked = {
        row.achievement.code
        for row in UserAchievement.query.filter_by(user_id=user.id).all()
    }
    newly = []
    for _ in range(3):  # 成就奖励的经验可能再触发经验类成就
        metrics = compute_metrics(user)
        changed = False
        for achievement in Achievement.query.order_by(Achievement.sort).all():
            if achievement.code in unlocked:
                continue
            if metrics.get(achievement.metric, 0) >= achievement.threshold:
                db.session.add(
                    UserAchievement(user_id=user.id, achievement_id=achievement.id)
                )
                _award_xp(user, achievement.xp_reward)
                unlocked.add(achievement.code)
                newly.append(achievement)
                changed = True
        if not changed:
            break
    return newly


def achievement_overview(user):
    metrics = compute_metrics(user)
    unlocked_rows = {
        row.achievement_id: row.unlocked_at
        for row in UserAchievement.query.filter_by(user_id=user.id).all()
    }
    rows = []
    for achievement in Achievement.query.order_by(Achievement.sort).all():
        current = min(metrics.get(achievement.metric, 0), achievement.threshold)
        rows.append(
            {
                "achievement": achievement,
                "unlocked": achievement.id in unlocked_rows,
                "unlocked_at": unlocked_rows.get(achievement.id),
                "current": metrics.get(achievement.metric, 0),
                "percent": round(current / achievement.threshold * 100),
            }
        )
    unlocked_count = sum(1 for row in rows if row["unlocked"])
    return rows, unlocked_count


# ---------------------------------------------------------------- 推荐
def get_recommendations(user, limit=4):
    done_ids = completed_ids(user)
    items = []
    used_lessons = set()

    started = []
    for course in Course.query.all():
        stats = course_stats(user, course, done_ids)
        if 0 < stats["completed"] < stats["total"]:
            started.append((course, stats))

    started.sort(key=lambda pair: pair[1]["completed"] / pair[1]["total"])
    for course, stats in started:
        lesson = next_lesson_for(user, course, done_ids)
        if lesson and lesson.id not in used_lessons:
            used_lessons.add(lesson.id)
            items.append(
                {
                    "type": "lesson",
                    "course": course,
                    "lesson": lesson,
                    "title": f"继续学习 · {lesson.title}",
                    "reason": f"{course.title} 已完成 {stats['completed']}/{stats['total']} 节，趁热打铁。",
                    "icon": KIND_ICONS.get(lesson.kind, "📘"),
                    "accent": course.language.gradient_from,
                }
            )
        if len(items) >= 2:
            break

    # 复习薄弱环节
    weak = (
        LessonProgress.query.filter_by(user_id=user.id, completed=True)
        .order_by(LessonProgress.best_score.asc())
        .first()
    )
    if weak and weak.lesson_id not in used_lessons and len(items) < limit:
        used_lessons.add(weak.lesson_id)
        lesson = db.session.get(Lesson, weak.lesson_id)
        if lesson:
            items.append(
                {
                    "type": "lesson",
                    "course": lesson.course,
                    "lesson": lesson,
                    "title": f"复习巩固 · {lesson.title}",
                    "reason": f"上次得分 {weak.best_score} 分，再练一次能记得更牢。",
                    "icon": "🔁",
                    "accent": lesson.course.language.gradient_from,
                }
            )

    # 尚未开始的语言
    started_language_ids = {
        db.session.get(Course, l.course_id).language_id
        for l in Lesson.query.filter(Lesson.id.in_(done_ids)).all()
        if db.session.get(Course, l.course_id)
    } if done_ids else set()

    for language in Language.query.order_by(Language.learners.desc()).all():
        if language.id in started_language_ids:
            continue
        course = Course.query.filter_by(language_id=language.id, level=1).first()
        if course and len(items) < limit:
            items.append(
                {
                    "type": "course",
                    "course": course,
                    "lesson": None,
                    "title": f"探索新语言 · {language.name}",
                    "reason": f"你还没有开始{language.name}，从 {course.level_code} 入门课起步正合适。",
                    "icon": language.flag,
                    "accent": language.gradient_from,
                }
            )
        if len(items) >= limit:
            break

    if not items:
        for language in Language.query.order_by(Language.learners.desc()).all()[:3]:
            course = Course.query.filter_by(language_id=language.id, level=1).first()
            if course:
                items.append(
                    {
                        "type": "course",
                        "course": course,
                        "lesson": None,
                        "title": f"开始学习 {language.name}",
                        "reason": f"从 {course.level_code} 起步，每天 10 分钟就能看到变化。",
                        "icon": language.flag,
                        "accent": language.gradient_from,
                    }
                )
    return items[:limit]


# ---------------------------------------------------------------- 课程载荷
def _options(correct, pool, position):
    distractors = []
    for value in pool:
        if value != correct and value not in distractors:
            distractors.append(value)
        if len(distractors) == 3:
            break
    options = distractors[:3]
    options.insert(min(position, len(options)), correct)
    return options, options.index(correct)


def lesson_payload(lesson):
    course = lesson.course
    language = course.language
    payload = {
        "id": lesson.id,
        "kind": lesson.kind,
        "title": lesson.title,
        "subtitle": lesson.subtitle,
        "xp": lesson.xp_reward,
        "course": {
            "id": course.id,
            "title": course.title,
            "level_code": course.level_code,
        },
        "language": {
            "code": language.code,
            "name": language.name,
            "flag": language.flag,
            "speech_code": language.speech_code,
        },
        "flashcards": [],
        "questions": [],
        "speaking": [],
    }

    words = course.words
    if lesson.kind == "vocab":
        meanings = [w.meaning for w in words]
        payload["flashcards"] = [
            {
                "term": w.term,
                "reading": w.reading,
                "pos": w.pos,
                "meaning": w.meaning,
                "example": w.example,
                "example_zh": w.example_zh,
            }
            for w in words
        ]
        for index, word in enumerate(words):
            options, answer = _options(word.meaning, meanings, index % 4)
            payload["questions"].append(
                {
                    "prompt": word.term,
                    "reading": word.reading,
                    "options": options,
                    "answer_index": answer,
                    "explanation": f"{word.term} 的意思是「{word.meaning}」。{word.example_zh}",
                    "audio": word.example,
                }
            )

    elif lesson.kind == "grammar":
        for index, item in enumerate(course.grammar_items):
            payload["questions"].append(
                {
                    "prompt": item.prompt,
                    "options": list(item.options),
                    "answer_index": item.answer_index,
                    "explanation": item.explanation,
                    "audio": "",
                }
            )

    elif lesson.kind == "listening":
        pool = [w.example_zh for w in words]
        selected = words[:6] if len(words) >= 6 else words
        for index, word in enumerate(selected):
            options, answer = _options(word.example_zh, pool, index % 4)
            payload["questions"].append(
                {
                    "prompt": "听音频，选出你听到句子的正确意思",
                    "audio": word.example,
                    "transcript": word.example,
                    "translation": word.example_zh,
                    "options": options,
                    "answer_index": answer,
                    "explanation": f"{word.example} —— {word.example_zh}",
                }
            )

    elif lesson.kind == "speaking":
        payload["speaking"] = [
            {
                "text": item.text,
                "reading": item.reading,
                "translation": item.translation,
                "tip": item.tip,
            }
            for item in course.speaking_items
        ]

    return payload


# ---------------------------------------------------------------- 统计
def build_stats(user):
    today = date.today()
    start = today - timedelta(days=13)
    logs = {
        log.day: log
        for log in StudyLog.query.filter(
            StudyLog.user_id == user.id, StudyLog.day >= start
        ).all()
    }
    series = []
    for offset in range(14):
        day = start + timedelta(days=offset)
        log = logs.get(day)
        series.append(
            {
                "date": day.isoformat(),
                "label": f"{day.month}/{day.day}",
                "xp": log.xp if log else 0,
                "minutes": log.minutes if log else 0,
            }
        )

    completed = LessonProgress.query.filter_by(user_id=user.id, completed=True).all()
    lessons = (
        Lesson.query.filter(Lesson.id.in_([row.lesson_id for row in completed])).all()
        if completed
        else []
    )

    skills = []
    for kind, label in KIND_LABELS.items():
        total = Lesson.query.filter_by(kind=kind).count()
        done = sum(1 for lesson in lessons if lesson.kind == kind)
        skills.append(
            {
                "kind": kind,
                "label": label,
                "icon": KIND_ICONS[kind],
                "total": total,
                "completed": done,
                "percent": round(done / total * 100) if total else 0,
            }
        )

    languages = []
    for row in language_overview(user):
        languages.append(
            {
                "code": row["language"].code,
                "name": row["language"].name,
                "flag": row["language"].flag,
                "color": row["language"].gradient_from,
                "total": row["total"],
                "completed": row["completed"],
                "percent": row["percent"],
            }
        )

    recent_rows = (
        LessonProgress.query.filter_by(user_id=user.id, completed=True)
        .order_by(LessonProgress.updated_at.desc())
        .limit(8)
        .all()
    )
    recent = []
    for row in recent_rows:
        lesson = row.lesson
        if not lesson:
            continue
        recent.append(
            {
                "lesson": lesson.title,
                "course": lesson.course.title,
                "language": lesson.course.language.name,
                "flag": lesson.course.language.flag,
                "kind": lesson.kind,
                "kind_label": KIND_LABELS.get(lesson.kind, lesson.kind),
                "score": row.best_score,
                "when": row.updated_at.strftime("%m月%d日 %H:%M") if row.updated_at else "",
            }
        )

    total_minutes = (
        db.session.query(db.func.coalesce(db.func.sum(StudyLog.minutes), 0))
        .filter(StudyLog.user_id == user.id)
        .scalar()
    )
    avg_score = round(sum(r.best_score for r in completed) / len(completed)) if completed else 0

    return {
        "series": series,
        "skills": skills,
        "languages": languages,
        "recent": recent,
        "totals": {
            "xp": user.total_xp,
            "streak": user.streak,
            "lessons": len(completed),
            "minutes": int(total_minutes or 0),
            "avg_score": avg_score,
            "words": compute_metrics(user)["words"],
        },
        "today": {
            "xp": user.today_xp(),
            "goal": user.daily_goal,
            "percent": min(100, round(user.today_xp() / user.daily_goal * 100))
            if user.daily_goal
            else 0,
        },
    }
