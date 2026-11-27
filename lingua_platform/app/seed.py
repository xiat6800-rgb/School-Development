"""数据库种子：课程内容、成就与社区演示数据（幂等）。"""
from datetime import date, datetime, timedelta

from .extensions import db
from .models import (
    Achievement,
    Comment,
    Course,
    GrammarItem,
    Language,
    Lesson,
    LessonProgress,
    Post,
    PostLike,
    SpeakingItem,
    StudyLog,
    User,
    UserAchievement,
    VocabItem,
)
from .seed_data import ACHIEVEMENTS, COURSES, DEMO_POSTS, DEMO_USERS, LANGUAGES, LESSON_META

LESSON_ORDER = ["vocab", "grammar", "listening", "speaking"]

DEMO_COURSE_SPECS = {
    "lily_en": [("en", 1, 4), ("en", 2, 2)],
    "haru_jp": [("ja", 1, 4), ("ja", 2, 3)],
    "minji_ko": [("ko", 1, 4), ("ko", 2, 4)],
    "azhe": [("en", 1, 4), ("ja", 1, 2)],
}
DEMO_WEEK_XP = [30, 45, 0, 60, 25, 40, 55]


def seed_all():
    if Language.query.count() == 0:
        _seed_courses()
    if Achievement.query.count() == 0:
        _seed_achievements()
    if Post.query.count() == 0:
        _seed_community()
    if LessonProgress.query.count() == 0:
        _seed_demo_activity()
    db.session.commit()


def _seed_courses():
    language_ids = {}
    for data in LANGUAGES:
        lang = Language(
            code=data["code"],
            name=data["name"],
            native_name=data["native_name"],
            flag=data["flag"],
            tagline=data["tagline"],
            description=data["description"],
            learners=data["learners"],
            gradient_from=data["gradient_from"],
            gradient_to=data["gradient_to"],
            greeting=data["greeting"],
            greeting_zh=data["greeting_zh"],
            speech_code=data["speech_code"],
        )
        db.session.add(lang)
        db.session.flush()
        language_ids[data["code"]] = lang.id

    for (code, level), data in COURSES.items():
        course = Course(
            language_id=language_ids[code],
            level=level,
            level_code=data["level_code"],
            title=data["title"],
            subtitle=data["subtitle"],
            tagline=data["tagline"],
            description=data["description"],
        )
        db.session.add(course)
        db.session.flush()

        for term, reading, pos, meaning, example, example_zh in data["words"]:
            db.session.add(
                VocabItem(
                    course_id=course.id,
                    term=term,
                    reading=reading,
                    pos=pos,
                    meaning=meaning,
                    example=example,
                    example_zh=example_zh,
                )
            )

        for prompt, options, answer_index, explanation in data["grammar"]:
            db.session.add(
                GrammarItem(
                    course_id=course.id,
                    prompt=prompt,
                    options=options,
                    answer_index=answer_index,
                    explanation=explanation,
                )
            )

        for text, reading, translation, tip in data["speaking"]:
            db.session.add(
                SpeakingItem(
                    course_id=course.id,
                    text=text,
                    reading=reading,
                    translation=translation,
                    tip=tip,
                )
            )

        subtitles = {
            "vocab": f"{len(data['words'])} 个核心词汇",
            "grammar": f"{len(data['grammar'])} 道语法精练",
            "listening": "听懂地道表达",
            "speaking": f"{len(data['speaking'])} 句跟读练习",
        }
        for index, kind in enumerate(LESSON_ORDER, start=1):
            meta = LESSON_META[kind]
            db.session.add(
                Lesson(
                    course_id=course.id,
                    order=index,
                    kind=kind,
                    title=meta["title"],
                    subtitle=subtitles[kind],
                    xp_reward=meta["xp"],
                    duration=meta["minutes"],
                )
            )


def _seed_achievements():
    for index, (code, name, desc, icon, metric, threshold, xp) in enumerate(
        ACHIEVEMENTS
    ):
        db.session.add(
            Achievement(
                code=code,
                name=name,
                description=desc,
                icon=icon,
                metric=metric,
                threshold=threshold,
                xp_reward=xp,
                sort=index,
            )
        )


def _seed_community():
    users = {}
    for data in DEMO_USERS:
        user = User.query.filter_by(username=data["username"]).first()
        if not user:
            user = User(
                username=data["username"],
                email=data["email"],
                display_name=data["display_name"],
                avatar_color=data["avatar_color"],
                bio=data["bio"],
                total_xp=data["total_xp"],
                streak=data["streak"],
            )
            user.set_password("demo1234")
            db.session.add(user)
            db.session.flush()
        users[data["username"]] = user

    usernames = list(users.keys())
    for index, data in enumerate(DEMO_POSTS):
        post = Post(
            user_id=users[data["author"]].id,
            language_code=data["language_code"],
            title=data["title"],
            content=data["content"],
        )
        db.session.add(post)
        db.session.flush()

        for comment_author, text in data["comments"]:
            db.session.add(
                Comment(
                    post_id=post.id,
                    user_id=users[comment_author].id,
                    content=text,
                )
            )

        # 为演示帖子补充点赞，让社区看起来更有活力
        for offset in range(1 + index % 4):
            liker = users[usernames[(index + offset + 1) % len(usernames)]]
            if liker.id != post.user_id:
                db.session.add(PostLike(post_id=post.id, user_id=liker.id))


def _seed_demo_activity():
    """为演示账号生成学习记录，让进度图表与推荐有真实内容。"""
    from .services import compute_metrics

    for username, specs in DEMO_COURSE_SPECS.items():
        user = User.query.filter_by(username=username).first()
        if not user:
            continue
        if LessonProgress.query.filter_by(user_id=user.id).count():
            continue

        for code, level, count in specs:
            language = Language.query.filter_by(code=code).first()
            if not language:
                continue
            course = Course.query.filter_by(
                language_id=language.id, level=level
            ).first()
            if not course:
                continue
            for index, lesson in enumerate(course.lessons[:count]):
                score = 78 + ((index * 11 + level * 7) % 22)
                finished = datetime.now() - timedelta(
                    days=(count - index) % 6, hours=index + 1
                )
                db.session.add(
                    LessonProgress(
                        user_id=user.id,
                        lesson_id=lesson.id,
                        best_score=score,
                        attempts=1,
                        completed=True,
                        completed_at=finished,
                        updated_at=finished,
                    )
                )

        for offset, xp in enumerate(DEMO_WEEK_XP):
            day = date.today() - timedelta(days=len(DEMO_WEEK_XP) - 1 - offset)
            db.session.add(
                StudyLog(
                    user_id=user.id,
                    day=day,
                    xp=xp,
                    minutes=round(xp / 3),
                    lessons=1 if xp else 0,
                )
            )
        user.last_study_date = date.today()
        db.session.flush()

        metrics = compute_metrics(user)
        unlocked = {
            row.achievement_id
            for row in UserAchievement.query.filter_by(user_id=user.id).all()
        }
        for achievement in Achievement.query.all():
            if achievement.id in unlocked:
                continue
            if metrics.get(achievement.metric, 0) >= achievement.threshold:
                db.session.add(
                    UserAchievement(
                        user_id=user.id, achievement_id=achievement.id
                    )
                )
