"""Application Factory。設定・拡張機能・Blueprint・CLI を登録する。"""

import os

from flask import Flask, render_template
from flask_login import current_user
from flask_wtf.csrf import CSRFError

from .clock import format_jst, seconds_between, to_jst, utcnow
from .config import Config
from .constants import (
    NOTIFICATION_TYPE_LABELS,
    WALLET_TYPE_LABELS,
)
from .extensions import csrf, db, login_manager, migrate


def create_app(config_object=None):
    """Flask アプリを生成する。"""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object or Config)

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_ROOT"], exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)

    from . import models  # noqa: F401  - モデル登録のため読み込む

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
        artworks_bp,
        auctions_bp,
        search_bp,
        favorites_bp,
        points_bp,
        notifications_bp,
    ):
        app.register_blueprint(blueprint)

    from .commands import register_commands

    register_commands(app)

    _register_template_helpers(app)
    _register_error_handlers(app)

    # 開発用: 未作成ならテーブルを作る（本番は flask db upgrade を使う）
    with app.app_context():
        db.create_all()

    return app


def _register_template_helpers(app):
    """テンプレートで共通利用する関数・値を登録する。"""

    @app.context_processor
    def inject_globals():
        from .services import notification_service

        unread = 0
        if current_user.is_authenticated:
            unread = notification_service.count_unread(current_user.id)
        return {
            "unread_notifications": unread,
            "now_utc": utcnow(),
            "to_jst": to_jst,
            "format_jst": format_jst,
            "seconds_between": seconds_between,
            "WALLET_TYPE_LABELS": WALLET_TYPE_LABELS,
            "NOTIFICATION_TYPE_LABELS": NOTIFICATION_TYPE_LABELS,
        }

    @app.template_filter("jst")
    def jst_filter(value, fmt="%Y/%m/%d %H:%M"):
        return format_jst(value, fmt)

    @app.template_filter("points")
    def points_filter(value):
        try:
            return f"{int(value):,}"
        except (TypeError, ValueError):
            return value


def _register_error_handlers(app):
    """エラー画面を日本語で返す。"""

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):  # noqa: ARG001
        return (
            render_template(
                "error.html",
                code=400,
                title="送信を確認できませんでした",
                message="画面を再読み込みして、もう一度操作してください。",
            ),
            400,
        )

    @app.errorhandler(400)
    def handle_bad_request(error):  # noqa: ARG001
        return (
            render_template(
                "error.html",
                code=400,
                title="リクエストが不正です",
                message="入力内容を確認してください。",
            ),
            400,
        )

    @app.errorhandler(403)
    def handle_forbidden(error):  # noqa: ARG001
        return (
            render_template(
                "error.html",
                code=403,
                title="操作できません",
                message="この操作を行う権限がありません。",
            ),
            403,
        )

    @app.errorhandler(404)
    def handle_not_found(error):  # noqa: ARG001
        return (
            render_template(
                "error.html",
                code=404,
                title="見つかりません",
                message="ページまたは作品が見つかりませんでした。",
            ),
            404,
        )

    @app.errorhandler(500)
    def handle_server_error(error):  # noqa: ARG001
        db.session.rollback()
        return (
            render_template(
                "error.html",
                code=500,
                title="処理できませんでした",
                message="時間をおいて、もう一度お試しください。",
            ),
            500,
        )
