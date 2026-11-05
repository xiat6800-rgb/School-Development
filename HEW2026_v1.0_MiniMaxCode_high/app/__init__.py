"""HEW2026 v1.0（MiniMax Code 版）のアプリケーションファクトリ。

設計方針（ロジック・ファイル構造 1章）：
- Application Factory + Blueprint で画面処理・業務ロジック・DB モデルを分離
"""

from __future__ import annotations

import os

from flask import Flask, jsonify, render_template

from app.config import get_config_by_name, upload_root
from app.extensions import csrf, db, login_manager, migrate
from app.services.errors import ServiceError


def create_app(config_name: str | None = None) -> Flask:
    """Flask アプリを生成する。"""
    app = Flask(__name__, instance_relative_config=True)

    name = config_name or os.environ.get("FLASK_CONFIG")
    app.config.from_object(get_config_by_name(name))

    if app.config.get("FLASK_ENV") == "production" and not app.config.get(
        "SECRET_KEY"
    ):
        raise RuntimeError("本番では SECRET_KEY を必ず設定してください。")

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    _register_user_loader()
    _register_blueprints(app)
    _register_error_handlers(app)
    _register_cli(app)
    _ensure_upload_dirs(app)

    return app


def _register_user_loader() -> None:
    """Flask-Login のユーザー取得コールバックを登録する。"""

    @login_manager.user_loader
    def load_user(user_id: str):
        from app.models.user import User

        return db.session.get(User, int(user_id))


def _register_blueprints(app: Flask) -> None:
    """Blueprint を登録する。"""
    from app.account.routes import account_bp
    from app.artworks.routes import artworks_bp
    from app.auctions.routes import auctions_bp
    from app.auth.routes import auth_bp
    from app.favorites.routes import favorites_bp
    from app.main.routes import main_bp
    from app.notifications.routes import notifications_bp
    from app.points.routes import points_bp
    from app.search.routes import search_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(artworks_bp)
    app.register_blueprint(auctions_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(favorites_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(points_bp)


def _register_error_handlers(app: Flask) -> None:
    """HTTP エラーの表示と、サービス層例外の変換を登録する。"""

    @app.errorhandler(ServiceError)
    def handle_service_error(error: ServiceError):
        from flask import flash, redirect, request, url_for

        if request.accept_mimetypes.best == "application/json":
            return jsonify({"ok": False, "message": error.message}), error.status_code

        from app.services.errors import NotFoundError, PermissionDeniedError

        if isinstance(error, PermissionDeniedError):
            return render_template("errors/403.html"), 403
        if isinstance(error, NotFoundError):
            return render_template("errors/404.html"), 404

        flash(error.message, "error")
        target = request.referrer or url_for("main.home")
        return redirect(target)

    @app.errorhandler(403)
    def handle_403(error):  # pragma: no cover - 表示のみ
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def handle_404(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def handle_500(error):  # pragma: no cover - 表示のみ
        return render_template("errors/500.html"), 500


def _register_cli(app: Flask) -> None:
    """CLI コマンドを登録する。"""
    from app.commands import register_commands

    register_commands(app)


def _ensure_upload_dirs(app: Flask) -> None:
    """アップロード先ディレクトリを用意する。"""
    root = upload_root(app.config["UPLOAD_FOLDER"])
    for subdir in ("artworks", "layers"):
        (root / subdir).mkdir(parents=True, exist_ok=True)
