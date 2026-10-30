"""Application Factory（要件定義書 7.4）。"""
import os

from flask import Flask, render_template
from flask_login import current_user
from flask_wtf.csrf import CSRFError

from app.config import BASE_DIR, get_config
from app.extensions import csrf, db, login_manager, migrate
from app.utils import format_jst, format_remaining


def create_app(config_object=None):
    app = Flask(__name__)
    app.config.from_object(config_object or get_config())

    upload_folder = app.config["UPLOAD_FOLDER"]
    if not os.path.isabs(upload_folder):
        upload_folder = os.path.join(BASE_DIR, upload_folder)
    app.config["UPLOAD_FOLDER"] = os.path.abspath(upload_folder)
    app.config["MAX_CONTENT_LENGTH"] = max(
        app.config["MAX_CONTENT_LENGTH"], app.config["MAX_IMAGE_BYTES"] * 2
    )

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.models import Notification, User

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    from app.account.routes import bp as account_bp
    from app.artworks.routes import bp as artworks_bp
    from app.auctions.routes import bp as auctions_bp
    from app.auth.routes import bp as auth_bp
    from app.favorites.routes import bp as favorites_bp
    from app.main.routes import bp as main_bp
    from app.notifications.routes import bp as notifications_bp
    from app.points.routes import bp as points_bp
    from app.search.routes import bp as search_bp

    for blueprint in (
        main_bp,
        auth_bp,
        artworks_bp,
        auctions_bp,
        search_bp,
        favorites_bp,
        account_bp,
        notifications_bp,
        points_bp,
    ):
        app.register_blueprint(blueprint)

    from app.commands import register_commands

    register_commands(app)

    app.jinja_env.filters["jst"] = format_jst
    app.jinja_env.filters["remaining"] = format_remaining

    @app.context_processor
    def inject_globals():
        unread = 0
        if current_user.is_authenticated:
            unread = (
                db.session.query(Notification)
                .filter(
                    Notification.user_id == current_user.id,
                    Notification.is_read.is_(False),
                )
                .count()
            )
        return {"unread_notifications": unread}

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        return (
            render_template(
                "errors/400.html",
                title="送信を確認できませんでした",
                message="画面の読み込みから時間が経過したか、送信内容が不正です。もう一度お試しください。",
            ),
            400,
        )

    @app.errorhandler(400)
    def handle_400(error):
        return render_template("errors/400.html", title="不正なリクエスト", message="入力内容を確認してください。"), 400

    @app.errorhandler(403)
    def handle_403(error):
        return render_template("errors/403.html", title="アクセスできません", message="このページを表示する権限がありません。"), 403

    @app.errorhandler(404)
    def handle_404(error):
        return render_template("errors/404.html", title="ページが見つかりません", message="URL が変更されたか、作品が削除された可能性があります。"), 404

    @app.errorhandler(413)
    def handle_413(error):
        return render_template("errors/400.html", title="データが大きすぎます", message="画像のサイズが上限を超えています。"), 413

    @app.errorhandler(500)
    def handle_500(error):
        db.session.rollback()
        return render_template("errors/500.html", title="処理に失敗しました", message="時間をおいてもう一度お試しください。"), 500

    return app
