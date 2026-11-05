from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db
from app.models import User
from app.services import auth_service, point_service
from app.services.event_service import EventClosedError, validate_event_operation

bp = Blueprint("auth", __name__)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        try:
            validate_event_operation("register")
        except EventClosedError:
            flash("イベントは終了したため新規登録できません。", "error")
            return redirect(url_for("auth.register"))
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        password_confirm = request.form.get("password_confirm") or ""
        error = None
        if not username or len(username) > 20:
            error = "ユーザー名は20文字以内で入力してください。"
        elif not username.isalnum():
            error = "ユーザー名は半角英数字で入力してください。"
        elif User.query.filter_by(username=username).first():
            error = "このユーザー名はすでに使われています。"
        elif len(password) < 8:
            error = "パスワードは8文字以上で入力してください。"
        elif password != password_confirm:
            error = "パスワード（確認）が一致しません。"
        if error:
            flash(error, "error")
            return render_template("auth/register.html", username=username)

        user = User(username=username, disp_name=username)
        user.set_password(password)
        recovery_code = auth_service.generate_recovery_code()
        user.set_recovery_code(recovery_code)
        db.session.add(user)
        db.session.flush()
        point_service.grant_register_bonus(user)
        db.session.commit()
        return render_template(
            "auth/register_done.html", recovery_code=recovery_code
        )
    return render_template("auth/register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = User.query.filter_by(username=username).first()
        if user is None or not user.check_password(password) or not user.is_active:
            flash("ユーザー名またはパスワードが正しくありません。", "error")
            return render_template("auth/login.html", username=username)
        login_user(user)
        next_url = request.args.get("next")
        return redirect(next_url or url_for("index"))
    return render_template("auth/login.html")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("ログアウトしました。", "success")
    return redirect(url_for("index"))


@bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    """ユーザー名と復旧コードでパスワードを再設定する。"""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        code = (request.form.get("recovery_code") or "").strip()
        password = request.form.get("password") or ""
        password_confirm = request.form.get("password_confirm") or ""
        user = User.query.filter_by(username=username).first()
        error = None
        if user is None or not user.check_recovery_code(code):
            error = "ユーザー名または復旧コードが正しくありません。"
        elif len(password) < 8:
            error = "パスワードは8文字以上で入力してください。"
        elif password != password_confirm:
            error = "パスワード（確認）が一致しません。"
        if error:
            flash(error, "error")
            return render_template("auth/reset_password.html")
        user.set_password(password)
        user.clear_recovery_code()
        db.session.commit()
        flash("パスワードを再設定しました。復旧コードは無効化されました。", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html")


@bp.route("/account", methods=["GET"])
@login_required
def show_account():
    from app.services import artwork_service

    drafts = artwork_service.list_user_drafts(current_user)
    artworks = artwork_service.list_user_artworks(current_user)
    return render_template(
        "auth/account.html", drafts=drafts, artworks=artworks
    )


@bp.route("/account/display-name", methods=["POST"])
@login_required
def update_display_name():
    disp_name = (request.form.get("disp_name") or "").strip()
    if not disp_name or len(disp_name) > 50:
        flash("表示名は50文字以内で入力してください。", "error")
    else:
        current_user.disp_name = disp_name
        db.session.commit()
        flash("表示名を更新しました。", "success")
    return redirect(url_for("auth.show_account"))


@bp.route("/account/recovery-code", methods=["POST"])
@login_required
def regenerate_recovery_code():
    password = request.form.get("password") or ""
    if not current_user.check_password(password):
        flash("現在のパスワードが正しくありません。", "error")
        return redirect(url_for("auth.show_account"))
    recovery_code = auth_service.generate_recovery_code()
    current_user.set_recovery_code(recovery_code)
    db.session.commit()
    return render_template(
        "auth/recovery_code.html", recovery_code=recovery_code
    )
