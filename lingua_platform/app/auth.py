"""注册、登录与退出。"""
import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from .extensions import db
from .models import User

bp = Blueprint("auth", __name__, url_prefix="/auth")

USERNAME_RE = re.compile(r"^[\w\u4e00-\u9fa5]{2,20}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
AVATAR_COLORS = ["#7c5cff", "#5b8cff", "#22d3ee", "#ff6b9d", "#ffb454", "#4ade80"]


def _safe_next(target):
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("main.dashboard")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""

        errors = []
        if not USERNAME_RE.match(username):
            errors.append("用户名需为 2-20 位字母、数字、下划线或中文。")
        if not EMAIL_RE.match(email):
            errors.append("请输入有效的邮箱地址。")
        if len(password) < 6:
            errors.append("密码至少需要 6 位。")
        if password != confirm:
            errors.append("两次输入的密码不一致。")
        if User.query.filter_by(username=username).first():
            errors.append("该用户名已被使用。")
        if User.query.filter_by(email=email).first():
            errors.append("该邮箱已注册，请直接登录。")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template(
                "auth/register.html", username=username, email=email
            )

        color = AVATAR_COLORS[sum(ord(ch) for ch in username) % len(AVATAR_COLORS)]
        user = User(
            username=username,
            email=email,
            display_name=username,
            avatar_color=color,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash(f"欢迎加入 LinguaFlow，{user.display_name}！", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("auth/register.html", username="", email="")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        identifier = (request.form.get("identifier") or "").strip()
        password = request.form.get("password") or ""

        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier.lower())
        ).first()

        if not user or not user.check_password(password):
            flash("用户名或密码不正确，请重试。", "error")
            return render_template("auth/login.html", identifier=identifier)

        login_user(user, remember=bool(request.form.get("remember")))
        flash(f"欢迎回来，{user.display_name}！", "success")
        return redirect(_safe_next(request.args.get("next")))

    return render_template("auth/login.html", identifier="")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("已退出登录，期待下次见面。", "info")
    return redirect(url_for("main.index"))
