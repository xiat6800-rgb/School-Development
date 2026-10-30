"""登録・ログイン・ログアウト。"""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import or_, select

from app.auth.forms import LoginForm, RegisterForm
from app.extensions import db
from app.models import User
from app.services.bonus_service import grant_signup_bonus

bp = Blueprint("auth", __name__, url_prefix="/auth")


def _safe_redirect_target():
    target = request.args.get("next", "")
    if target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("account.index")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("account.index"))

    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        email = form.email.data.strip().lower()

        existing = db.session.execute(
            select(User).where(or_(User.username == username, User.email == email))
        ).scalar_one_or_none()
        if existing is not None:
            message = (
                "このユーザー名は使用されています。"
                if existing.username == username
                else "このメールアドレスは登録済みです。"
            )
            flash(message, "error")
        else:
            user = User(username=username, email=email, disp_name="", role="user")
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.flush()
            # 表示名の初期値は Flask 側で user{id} を設定する（DB設計書 4.1）
            user.disp_name = f"user{user.id}"
            grant_signup_bonus(user)
            db.session.commit()

            login_user(user)
            flash("登録が完了しました。ボーナスポイントを付与しました。", "success")
            return redirect(url_for("account.index"))

    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("account.index"))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = db.session.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()
        if user is None or not user.check_password(form.password.data):
            flash("メールアドレスまたはパスワードが正しくありません。", "error")
        elif not user.is_active:
            flash("このアカウントは現在利用できません。", "error")
        else:
            login_user(user)
            flash(f"{user.disp_name} さん、おかえりなさい。", "success")
            return redirect(_safe_redirect_target())

    return render_template("auth/login.html", form=form)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("ログアウトしました。", "info")
    return redirect(url_for("main.home"))
