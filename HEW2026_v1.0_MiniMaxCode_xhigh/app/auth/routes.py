"""登録・ログイン・ログアウト・パスワード再設定。

仕様決定事項1章に従い、メールアドレスは入力も保存もしない。
"""

from __future__ import annotations

from flask import (
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_user, logout_user

from app.auth import auth_bp
from app.extensions import db
from app.services import auth_service
from app.services.errors import ServiceError
from app.services.point_service import grant_signup_bonus


@auth_bp.route("/auth/register", methods=["GET", "POST"])
def register():
    """新規登録する。復旧コードを 1 回だけ表示する。"""
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")
        try:
            if password != password_confirm:
                raise ServiceError("パスワードが一致しません。")
            user, recovery_code = auth_service.register_user(username, password)
            grant_signup_bonus(
                user, int(current_app.config["BONUS_SIGNUP_POINTS"])
            )
            db.session.commit()
        except ServiceError as error:
            db.session.rollback()
            flash(error.message, "error")
            return render_template("auth/register.html", username=username)

        login_user(user)
        flash("登録が完了しました。復旧コードを必ず保管してください。", "success")
        return render_template(
            "auth/recovery_code.html",
            recovery_code=recovery_code,
            is_first_time=True,
        )

    return render_template("auth/register.html", username="")


@auth_bp.route("/auth/login", methods=["GET", "POST"])
def login():
    """ユーザー名とパスワードでログインする。"""
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))
        try:
            user = auth_service.authenticate(username, password)
        except ServiceError as error:
            flash(error.message, "error")
            return render_template("auth/login.html", username=username)

        login_user(user, remember=remember)
        flash("ログインしました。", "success")
        return redirect(_safe_next(request.args.get("next")))

    return render_template("auth/login.html", username="")


@auth_bp.route("/auth/logout", methods=["POST"])
def logout():
    """ログインセッションを終了する。"""
    logout_user()
    flash("ログアウトしました。", "success")
    return redirect(url_for("main.home"))


@auth_bp.route("/auth/recover", methods=["GET", "POST"])
def recover():
    """ユーザー名と復旧コードでパスワードを再設定する。"""
    if request.method == "POST":
        username = request.form.get("username", "")
        code = request.form.get("recovery_code", "")
        new_password = request.form.get("new_password", "")
        confirm = request.form.get("new_password_confirm", "")
        try:
            if new_password != confirm:
                raise ServiceError("パスワードが一致しません。")
            auth_service.reset_password_with_code(username, code, new_password)
            db.session.commit()
        except ServiceError as error:
            db.session.rollback()
            flash(error.message, "error")
            return render_template("auth/recover.html", username=username)

        flash("パスワードを再設定しました。新しいパスワードでログインしてください。", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/recover.html", username="")


def _safe_next(target: str | None) -> str:
    """ログイン後の遷移先。外部サイトへの遷移を防ぐ。"""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("main.home")
