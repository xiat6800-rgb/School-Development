from flask import Flask, flash, jsonify, redirect, request, url_for
from flask_login import current_user
from flask_wtf.csrf import CSRFError

from app.commands import register_commands
from app.config import Config
from app.extensions import csrf, db, login_manager, migrate
from app.models import Notification, User
from app.services.common import BusinessError
from app.utils import to_jst


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.account import bp as account_bp
    from app.admin import bp as admin_bp
    from app.artworks import bp as artworks_bp
    from app.auctions import bp as auctions_bp
    from app.auth import bp as auth_bp
    from app.comments import bp as comments_bp
    from app.favorites import bp as favorites_bp
    from app.main import bp as main_bp
    from app.notifications import bp as notifications_bp
    from app.points import bp as points_bp
    from app.search import bp as search_bp
    from app.streams import bp as streams_bp

    for blueprint in (
        main_bp, auth_bp, account_bp, artworks_bp, auctions_bp, streams_bp,
        comments_bp, favorites_bp, notifications_bp, points_bp, search_bp, admin_bp,
    ):
        app.register_blueprint(blueprint)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.template_filter("jst")
    def format_jst(value, fmt="%Y/%m/%d %H:%M"):
        return to_jst(value).strftime(fmt) if value else "—"

    @app.template_filter("status_jp")
    def status_jp(value):
        labels = {
            "draft": "下書き", "listed": "出品中", "sold": "落札済み",
            "unsold": "未落札", "cancelled": "取消済み", "active": "開催中",
            "ended": "終了", "ready": "配信前", "live": "配信中",
            "paused": "一時中断", "visible": "公開", "hidden": "非表示",
            "deleted": "削除済み",
        }
        return labels.get(value, value)

    @app.context_processor
    def inject_globals():
        unread = 0
        if current_user.is_authenticated:
            unread = Notification.query.filter_by(
                user_id=current_user.id, is_read=False
            ).count()
        return {
            "unread_notifications": unread,
            "event_ends_at": app.config["EVENT_ENDS_AT"],
            "app_ends_at": app.config["APP_ENDS_AT"],
        }

    @app.errorhandler(BusinessError)
    def handle_business_error(error):
        db.session.rollback()
        if request.is_json or request.accept_mimetypes.best == "application/json":
            return jsonify({"ok": False, "error": str(error)}), 400
        flash(str(error), "error")
        return redirect(request.referrer or url_for("main.index"))

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        if request.is_json:
            return jsonify({"ok": False, "error": "CSRFトークンを確認してください。"}), 400
        flash("フォームの有効期限が切れました。もう一度操作してください。", "error")
        return redirect(request.referrer or url_for("main.index"))

    @app.errorhandler(403)
    def forbidden(error):
        return app.jinja_env.get_or_select_template("errors/403.html").render(), 403

    @app.errorhandler(404)
    def not_found(error):
        return app.jinja_env.get_or_select_template("errors/404.html").render(), 404

    register_commands(app)
    return app
