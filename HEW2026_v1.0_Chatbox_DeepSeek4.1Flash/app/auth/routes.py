"""認証・アカウント関連のルート。"""

import re

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import IntegrityError

from ..constants import BONUS_REGISTRATION, EVENT_OPERATION_REGISTER
from ..extensions import db
from ..models import User
from ..services import (
    artwork_service,
    auction_service,
    event_service,
    favorite_service,
    notification_service,
    point_service,
)
from ..services.errors import DomainError

bp = Blueprint("auth", __name__, url_prefix="/auth")

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,20}$")
PASSWORD_MIN_LENGTH = 8


def _validate_new_password(password, confirm):
    """パスワードの条件を検証し、エラーの一覧を返す。"""
    errors = []
    if len(password or "") < PASSWORD_MIN_LENGTH:
        errors.append(f"パスワードは{PASSWORD_MIN_LENGTH}文字以上にしてください。")
    if password != confirm:
        errors.append("パスワード（確認）が一致しません。")
    return errors


@bp.route("/register", methods=["GET", "POST"])
def register():
    """ユーザー名とパスワードで登録し、復旧コードを一度だけ表示する。"""
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = {"username": ""}
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("password_confirm") or ""
        form["username"] = username

        errors = []
        if not USERNAME_PATTERN.match(username):
            errors.append(
                "ユーザー名は英数字とアンダースコア3〜20文字で入力してください。"
            )
        errors.extend(_validate_new_password(password, confirm))
        if db.session.scalar(db.select(User).where(User.username == username)):
            errors.append("このユーザー名は既に使用されています。")

        if not errors:
            try:
                event_service.validate_event_operation(EVENT_OPERATION_REGISTER)
                user = User(username=username, disp_name=username)
                user.set_password(password)
                recovery_code = user.issue_recovery_code()
                db.session.add(user)
                db.session.flush()
                # 表示名の初期値は user{id}
                user.disp_name = f"user{user.id}"
                point_service.grant_bonus_points(user, BONUS_REGISTRATION)
                db.session.commit()
            except DomainError as error:
                db.session.rollback()
                errors.append(str(error))
            except IntegrityError:
                db.session.rollback()
                errors.append("このユーザー名は既に使用されています。")
            else:
                login_user(user)
                return render_template(
                    "auth/recovery_code.html",
                    recovery_code=recovery_code,
                    is_new_account=True,
                )

        for message in errors:
            flash(message, "error")

    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    """ユーザー名とパスワードでログインする。"""
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = {"username": ""}
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        form["username"] = username

        user = db.session.scalar(db.select(User).where(User.username == username))
        if user is None or not user.check_password(password):
            flash("ユーザー名またはパスワードが正しくありません。", "error")
        elif not user.is_active:
            flash("このアカウントは現在利用できません。", "error")
        else:
            login_user(user)
            flash("ログインしました。", "success")
            next_url = request.args.get("next")
            if next_url and next_url.startswith("/"):
                return redirect(next_url)
            return redirect(url_for("main.index"))

    return render_template("auth/login.html", form=form)


@bp.post("/logout")
@login_required
def logout():
    """ログインセッションを終了する。"""
    logout_user()
    flash("ログアウトしました。", "success")
    return redirect(url_for("main.index"))


@bp.route("/recover", methods=["GET", "POST"])
def recover():
    """ユーザー名と復旧コードでパスワードを再設定する。"""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        recovery_code = (request.form.get("recovery_code") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("password_confirm") or ""

        user = db.session.scalar(db.select(User).where(User.username == username))
        if user is None or not user.verify_recovery_code(recovery_code):
            flash("ユーザー名または復旧コードが正しくありません。", "error")
            return render_template("auth/recover.html", form={"username": username})

        errors = _validate_new_password(password, confirm)
        if not errors:
            user.set_password(password)
            user.invalidate_recovery_code()
            db.session.commit()
            flash(
                "パスワードを再設定しました。新しい復旧コードは発行されません。",
                "success",
            )
            return redirect(url_for("auth.login"))

        for message in errors:
            flash(message, "error")
        return render_template("auth/recover.html", form={"username": username})

    return render_template("auth/recover.html", form={"username": ""})


@bp.get("/account")
@login_required
def show_account():
    """本人のアカウント画面。下書き・お気に入り・出品をまとめて表示する。"""
    drafts = artwork_service.list_user_drafts(current_user.id)
    return render_template(
        "account/index.html",
        drafts=drafts,
        artwork_favorites=favorite_service.list_artwork_favorites(current_user.id),
        auction_favorites=favorite_service.list_auction_favorites(current_user.id),
        my_auctions=auction_service.list_user_auctions(current_user.id),
        transactions=point_service.list_point_transactions(current_user.id, limit=10),
        bonuses=point_service.list_user_bonuses(current_user.id, limit=10),
    )


@bp.post("/account/display-name")
@login_required
def update_display_name():
    """表示名を更新する。一意制約はなく、ユーザー名とは別に管理する。"""
    disp_name = (request.form.get("disp_name") or "").strip()
    if not 1 <= len(disp_name) <= 50:
        flash("表示名は1〜50文字で入力してください。", "error")
        return redirect(url_for("auth.show_account"))

    current_user.disp_name = disp_name
    db.session.commit()
    flash("表示名を更新しました。", "success")
    return redirect(url_for("auth.show_account"))


@bp.post("/account/recovery-code")
@login_required
def regenerate_recovery_code():
    """パスワードを確認して復旧コードを再発行する（旧コードは無効化）。"""
    password = request.form.get("password") or ""
    if not current_user.check_password(password):
        flash("パスワードが正しくありません。", "error")
        return redirect(url_for("auth.show_account"))

    recovery_code = current_user.issue_recovery_code()
    db.session.commit()
    return render_template(
        "auth/recovery_code.html",
        recovery_code=recovery_code,
        is_new_account=False,
    )


@bp.get("/account/notifications")
@login_required
def account_notifications():
    """未読通知数を確認するための補助導線。"""
    return redirect(url_for("notifications.index"))


@bp.get("/account/transactions")
@login_required
def account_transactions():
    return redirect(url_for("points.transactions"))
