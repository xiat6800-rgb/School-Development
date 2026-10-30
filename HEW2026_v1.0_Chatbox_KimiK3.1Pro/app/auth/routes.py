from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.auth import bp
from app.extensions import db
from app.models import User
from app.services.auth_service import generate_recovery_code, normalize_recovery_code
from app.services.common import BusinessError
from app.services.event_service import validate_event_operation
from app.services.point_service import grant_bonus_points
from app.utils import utcnow


def _safe_next(target):
    return target if target and target.startswith("/") and not target.startswith("//") else None


@bp.route("/register", methods=("GET", "POST"))
def register():
    if current_user.is_authenticated:
        return redirect(url_for("account.show_account"))
    if request.method == "POST":
        validate_event_operation("register")
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirmation = request.form.get("password_confirm", "")
        if not 2 <= len(username) <= 20:
            raise BusinessError("ユーザー名は2〜20文字で入力してください。")
        if len(password) < 8:
            raise BusinessError("パスワードは8文字以上で入力してください。")
        if password != confirmation:
            raise BusinessError("確認用パスワードが一致しません。")
        if User.query.filter_by(username=username).first():
            raise BusinessError("このユーザー名はすでに使われています。")
        code = generate_recovery_code()
        user = User(username=username, display_name=username)
        user.set_password(password)
        user.set_recovery_code(code)
        db.session.add(user)
        db.session.flush()
        grant_bonus_points(user, "register")
        db.session.commit()
        login_user(user)
        return render_template("auth/recovery_code.html", recovery_code=code, first=True)
    return render_template("auth/register.html")


@bp.route("/login", methods=("GET", "POST"))
def login():
    if current_user.is_authenticated:
        return redirect(url_for("account.show_account"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password) or not user.is_active:
            raise BusinessError("ユーザー名またはパスワードが正しくありません。")
        login_user(user, remember=request.form.get("remember") == "1")
        return redirect(_safe_next(request.args.get("next")) or url_for("main.index"))
    return render_template("auth/login.html")


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    flash("ログアウトしました。", "success")
    return redirect(url_for("main.index"))


@bp.route("/reset", methods=("GET", "POST"))
def reset_password():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        code = normalize_recovery_code(request.form.get("recovery_code"))
        password = request.form.get("password", "")
        if len(password) < 8 or password != request.form.get("password_confirm"):
            raise BusinessError("新しいパスワードは8文字以上で、確認欄と同じ値にしてください。")
        user = User.query.filter_by(username=username).first()
        if not user or not user.check_recovery_code(code):
            raise BusinessError("ユーザー名または復旧コードが正しくありません。")
        user.set_password(password)
        user.recovery_code_used_at = utcnow()
        user.recovery_code_hash = None
        db.session.commit()
        flash("パスワードを再設定しました。旧復旧コードは無効です。", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset.html")


@bp.post("/recovery-code")
@login_required
def regenerate_recovery_code():
    if not current_user.check_password(request.form.get("password", "")):
        raise BusinessError("現在のパスワードが正しくありません。")
    code = generate_recovery_code()
    current_user.set_recovery_code(code)
    db.session.commit()
    return render_template("auth/recovery_code.html", recovery_code=code, first=False)
