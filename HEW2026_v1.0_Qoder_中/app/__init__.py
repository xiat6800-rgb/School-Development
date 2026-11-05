"""Application Factory。設定・拡張機能・Blueprint・CLI を登録する。"""
from datetime import datetime, timedelta, timezone

from flask import Flask

from .config import get_config
from .extensions import csrf, db, login_manager, migrate


def create_app(config_name="development"):
    app = Flask(__name__)
    app.config.from_object(get_config(config_name))

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    from . import models  # noqa: F401  (create_all / migrate 対象の登録)
    from .models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from .artworks import bp as artworks_bp
    from .auctions import bp as auctions_bp
    from .auth import bp as auth_bp
    from .favorites import bp as favorites_bp
    from .main import bp as main_bp
    from .notifications import bp as notifications_bp
    from .points import bp as points_bp
    from .search import bp as search_bp

    for blueprint in (
        main_bp,
        auth_bp,
        auctions_bp,
        search_bp,
        favorites_bp,
        points_bp,
        notifications_bp,
    ):
        app.register_blueprint(blueprint)
    app.register_blueprint(artworks_bp, url_prefix="/artworks")

    from .commands import register_commands

    register_commands(app)

    @app.template_filter("jst")
    def jst_filter(value):
        """UTC datetime を日本時間の文字列へ変換する（要件定義書 7.3）。"""
        if value is None:
            return ""
        return (value + timedelta(hours=9)).strftime("%Y/%m/%d %H:%M:%S")

    @app.context_processor
    def inject_globals():
        from .models.notification import Notification
        from flask_login import current_user

        unread = 0
        if current_user.is_authenticated:
            unread = (
                Notification.query.filter_by(
                    user_id=current_user.id, is_read=False
                ).count()
            )
        return {
            "unread_notifications": unread,
            "utc_now": datetime.now(timezone.utc).replace(tzinfo=None),
        }

    with app.app_context():
        if app.config["TESTING"] or app.config.get("SQLALCHEMY_DATABASE_URI", "").startswith("sqlite"):
            db.create_all()

    return app
