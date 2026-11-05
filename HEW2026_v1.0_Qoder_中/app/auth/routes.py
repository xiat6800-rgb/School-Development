"""認証・アカウントのルート。ユーザー名認証でメールは一切使わない。"""
from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from .. import services
from ..extensions import db
from ..favorites.helpers import list_artwork_favorites, list_auction_favorites
from ..models.artwork import Artwork
from ..models.user import User
from ..services import point_service
from . import bp


@bp.route("/register", methods=["GET", "POST"])
def register():
    """ユーザー名とパスワードを検証して登録し、表示名の初期値を設定する。"""
    if current_user.is_authenticated:
        return redirect(url_for("main.show_top"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if not username or len(username) > 20:
            flash("ユーザー名は 1〜20 文字で入力してください。", "error")
        elif len(password) < 4:
            flash("パスワードは 4 文字以上で入力してください。", "error")
        elif User.query.filter_by(username=username).first():
            flash("このユーザー名は既に使われています。", "error")
        else:
            try:
                services.event_service.validate_event_operation("新規登録")
            except services.event_service.EventClosedError as exc:
                flash(str(exc), "error")
                return render_template("auth/register.html")
            user = User(username=username, disp_name="")
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            user.disp_name = f"user{user.id}"
            code = services.auth_service.issue_recovery_code(user)
            point_service.grant_bonus_points(
                user, "signup", f"signup:{user.id}"
            )
            db.session.commit()
            login_user(user)
            # 復旧コードは登録時に一度だけ表示する
            return render_template("auth/recovery_code.html", code=code, first=True)
    return render_template("auth/register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    """ユーザー名とパスワードを検証し、ログインセッションを開始する。"""
    if current_user.is_authenticated:
        return redirect(url_for("main.show_top"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = User.query.filter_by(username=username).first()
        if user and user.is_active and user.check_password(password):
            login_user(user)
            next_url = request.args.get("next")
            return redirect(next_url or url_for("main.show_top"))
        flash("ユーザー名またはパスワードが正しくありません。", "error")
    return render_template("auth/login.html")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    """ログインセッションを終了する。"""
    logout_user()
    return redirect(url_for("main.show_top"))


@bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    """ユーザー名と復旧コードでパスワードを再設定し、コードを無効化する。"""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        code = (request.form.get("recovery_code") or "").strip()
        new_password = request.form.get("new_password") or ""
        user = User.query.filter_by(username=username).first()
        if not user or not user.check_recovery_code(code):
            flash("ユーザー名または復旧コードが正しくありません。", "error")
        elif len(new_password) < 4:
            flash("パスワードは 4 文字以上で入力してください。", "error")
        else:
            user.set_password(new_password)
            user.invalidate_recovery_code()
            db.session.commit()
            flash("パスワードを再設定しました。新しいパスワードでログインしてください。", "info")
            return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html")


@bp.route("/account")
@login_required
def show_account():
    """本人のアカウント画面（下書き・お気に入り・残高・履歴）。"""
    drafts = services.artwork_service.list_user_drafts(current_user)
    artworks = (
        Artwork.query.filter(Artwork.artist_id == current_user.id)
        .order_by(Artwork.created_at.desc())
        .all()
    )
    artwork_favorites = list_artwork_favorites(current_user)
    auction_favorites = list_auction_favorites(current_user)
    transactions = point_service.list_point_transactions(current_user)
    return render_template(
        "auth/account.html",
        drafts=drafts,
        artworks=artworks,
        artwork_favorites=artwork_favorites,
        auction_favorites=auction_favorites,
        transactions=transactions,
    )


@bp.route("/account/display-name", methods=["POST"])
@login_required
def update_display_name():
    """本人の表示名を更新する。"""
    name = (request.form.get("disp_name") or "").strip()
    if not name or len(name) > 50:
        flash("表示名は 1〜50 文字で入力してください。", "error")
    else:
        current_user.disp_name = name
        db.session.commit()
        flash("表示名を更新しました。", "info")
    return redirect(url_for("auth.show_account"))


@bp.route("/account/recovery-code", methods=["POST"])
@login_required
def regenerate_recovery_code():
    """ログイン中にパスワードを確認し、旧コードを無効にして新コードを一度表示。"""
    password = request.form.get("password") or ""
    if not current_user.check_password(password):
        flash("パスワードが正しくありません。", "error")
        return redirect(url_for("auth.show_account"))
    code = services.auth_service.issue_recovery_code(current_user)
    db.session.commit()
    return render_template("auth/recovery_code.html", code=code, first=False)
