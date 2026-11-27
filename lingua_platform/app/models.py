"""数据模型：用户、语言、课程、学习内容、进度、成就与社区。"""
from datetime import date, datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def now():
    return datetime.now()


LEVEL_NAMES = [
    "初来乍到",
    "语言学徒",
    "学习探索者",
    "进阶旅人",
    "流利表达者",
    "语言大师",
]
LEVEL_STEP = 200


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(48), nullable=False, default="学习者")
    avatar_color = db.Column(db.String(16), default="#7c5cff")
    bio = db.Column(db.String(200), default="")
    daily_goal = db.Column(db.Integer, default=30, nullable=False)
    total_xp = db.Column(db.Integer, default=0, nullable=False)
    streak = db.Column(db.Integer, default=0, nullable=False)
    last_study_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=now, nullable=False)

    progress = db.relationship(
        "LessonProgress", back_populates="user", cascade="all, delete-orphan"
    )
    study_logs = db.relationship(
        "StudyLog", back_populates="user", cascade="all, delete-orphan"
    )
    achievements = db.relationship(
        "UserAchievement", back_populates="user", cascade="all, delete-orphan"
    )
    posts = db.relationship("Post", back_populates="author", cascade="all, delete-orphan")
    comments = db.relationship(
        "Comment", back_populates="author", cascade="all, delete-orphan"
    )
    likes = db.relationship("PostLike", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    @property
    def level(self):
        return min(6, self.total_xp // LEVEL_STEP + 1)

    @property
    def level_name(self):
        return LEVEL_NAMES[self.level - 1]

    @property
    def level_xp(self):
        if self.level >= 6:
            return LEVEL_STEP
        return self.total_xp % LEVEL_STEP

    @property
    def level_percent(self):
        if self.level >= 6:
            return 100
        return round(self.level_xp / LEVEL_STEP * 100)

    @property
    def initial(self):
        return (self.display_name or self.username or "L")[0].upper()

    def today_xp(self):
        log = StudyLog.query.filter_by(user_id=self.id, day=date.today()).first()
        return log.xp if log else 0


class Language(db.Model):
    __tablename__ = "languages"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(8), unique=True, nullable=False)
    name = db.Column(db.String(32), nullable=False)
    native_name = db.Column(db.String(48), nullable=False)
    flag = db.Column(db.String(16), default="🌐")
    tagline = db.Column(db.String(120), default="")
    description = db.Column(db.String(400), default="")
    learners = db.Column(db.Integer, default=0)
    gradient_from = db.Column(db.String(16), default="#5b8cff")
    gradient_to = db.Column(db.String(16), default="#7c5cff")
    greeting = db.Column(db.String(64), default="Hello")
    greeting_zh = db.Column(db.String(64), default="你好")
    speech_code = db.Column(db.String(16), default="en-US")

    courses = db.relationship(
        "Course", back_populates="language", order_by="Course.level"
    )


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    language_id = db.Column(db.Integer, db.ForeignKey("languages.id"), nullable=False)
    level = db.Column(db.Integer, nullable=False, default=1)
    level_code = db.Column(db.String(8), nullable=False, default="A1")
    title = db.Column(db.String(80), nullable=False)
    subtitle = db.Column(db.String(160), default="")
    description = db.Column(db.String(400), default="")
    tagline = db.Column(db.String(120), default="")

    language = db.relationship("Language", back_populates="courses")
    lessons = db.relationship(
        "Lesson",
        back_populates="course",
        order_by="Lesson.order",
        cascade="all, delete-orphan",
    )
    words = db.relationship(
        "VocabItem",
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="VocabItem.id",
    )
    grammar_items = db.relationship(
        "GrammarItem", back_populates="course", cascade="all, delete-orphan"
    )
    speaking_items = db.relationship(
        "SpeakingItem", back_populates="course", cascade="all, delete-orphan"
    )

    @property
    def status_label(self):
        return {1: "入门", 2: "进阶", 3: "高阶"}.get(self.level, "入门")


class Lesson(db.Model):
    __tablename__ = "lessons"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    order = db.Column(db.Integer, nullable=False, default=1)
    kind = db.Column(db.String(16), nullable=False)  # vocab / grammar / listening / speaking
    title = db.Column(db.String(80), nullable=False)
    subtitle = db.Column(db.String(160), default="")
    xp_reward = db.Column(db.Integer, default=30)
    duration = db.Column(db.Integer, default=6)

    course = db.relationship("Course", back_populates="lessons")
    progress = db.relationship(
        "LessonProgress", back_populates="lesson", cascade="all, delete-orphan"
    )


class VocabItem(db.Model):
    __tablename__ = "vocab_items"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    term = db.Column(db.String(120), nullable=False)
    reading = db.Column(db.String(160), default="")
    pos = db.Column(db.String(24), default="")
    meaning = db.Column(db.String(160), nullable=False)
    example = db.Column(db.String(300), default="")
    example_zh = db.Column(db.String(300), default="")

    course = db.relationship("Course", back_populates="words")


class GrammarItem(db.Model):
    __tablename__ = "grammar_items"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    prompt = db.Column(db.String(300), nullable=False)
    options = db.Column(db.JSON, nullable=False)
    answer_index = db.Column(db.Integer, nullable=False, default=0)
    explanation = db.Column(db.String(400), default="")

    course = db.relationship("Course", back_populates="grammar_items")


class SpeakingItem(db.Model):
    __tablename__ = "speaking_items"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    text = db.Column(db.String(300), nullable=False)
    reading = db.Column(db.String(300), default="")
    translation = db.Column(db.String(300), default="")
    tip = db.Column(db.String(200), default="")

    course = db.relationship("Course", back_populates="speaking_items")


class LessonProgress(db.Model):
    __tablename__ = "lesson_progress"
    __table_args__ = (db.UniqueConstraint("user_id", "lesson_id", name="uq_user_lesson"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id"), nullable=False)
    best_score = db.Column(db.Integer, default=0)
    attempts = db.Column(db.Integer, default=0)
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=now, onupdate=now)

    user = db.relationship("User", back_populates="progress")
    lesson = db.relationship("Lesson", back_populates="progress")


class StudyLog(db.Model):
    __tablename__ = "study_logs"
    __table_args__ = (db.UniqueConstraint("user_id", "day", name="uq_user_day"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    day = db.Column(db.Date, nullable=False)
    xp = db.Column(db.Integer, default=0)
    minutes = db.Column(db.Integer, default=0)
    lessons = db.Column(db.Integer, default=0)

    user = db.relationship("User", back_populates="study_logs")


class Achievement(db.Model):
    __tablename__ = "achievements"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(48), unique=True, nullable=False)
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.String(200), default="")
    icon = db.Column(db.String(16), default="🏅")
    metric = db.Column(db.String(24), nullable=False)
    threshold = db.Column(db.Integer, default=1)
    xp_reward = db.Column(db.Integer, default=20)
    sort = db.Column(db.Integer, default=0)

    unlocks = db.relationship(
        "UserAchievement", back_populates="achievement", cascade="all, delete-orphan"
    )


class UserAchievement(db.Model):
    __tablename__ = "user_achievements"
    __table_args__ = (
        db.UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    achievement_id = db.Column(
        db.Integer, db.ForeignKey("achievements.id"), nullable=False
    )
    unlocked_at = db.Column(db.DateTime, default=now)

    user = db.relationship("User", back_populates="achievements")
    achievement = db.relationship("Achievement", back_populates="unlocks")


class Post(db.Model):
    __tablename__ = "posts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    language_code = db.Column(db.String(8), default="all")
    title = db.Column(db.String(140), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=now, nullable=False)

    author = db.relationship("User", back_populates="posts")
    comments = db.relationship(
        "Comment",
        back_populates="post",
        cascade="all, delete-orphan",
        order_by="Comment.created_at",
    )
    likes = db.relationship(
        "PostLike", back_populates="post", cascade="all, delete-orphan"
    )

    @property
    def like_count(self):
        return len(self.likes)


class PostLike(db.Model):
    __tablename__ = "post_likes"
    __table_args__ = (db.UniqueConstraint("user_id", "post_id", name="uq_user_post_like"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=now, nullable=False)

    user = db.relationship("User", back_populates="likes")
    post = db.relationship("Post", back_populates="likes")


class Comment(db.Model):
    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    content = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=now, nullable=False)

    post = db.relationship("Post", back_populates="comments")
    author = db.relationship("User", back_populates="comments")
