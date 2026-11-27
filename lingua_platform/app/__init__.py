"""LinguaFlow 应用工厂。"""
import os

from flask import Flask, flash, jsonify, redirect, request, url_for
from flask_wtf.csrf import CSRFError

from .extensions import csrf, db, login_manager


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    os.makedirs(os.path.join(base_dir, "instance"), exist_ok=True)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "linguaflow-dev-secret-2026"),
        SQLALCHEMY_DATABASE_URI="sqlite:///"
        + os.path.join(base_dir, "instance", "lingua.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        WTF_CSRF_TIME_LIMIT=None,
        JSON_AS_ASCII=False,
    )

    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "请先登录后再开始学习。"
    login_manager.login_message_category = "info"

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        flash(login_manager.login_message, "info")
        return redirect(url_for("auth.login", next=request.path))

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": "csrf"}), 400
        return "CSRF 校验失败，请刷新页面后重试。", 400

    @app.template_filter("xp_comma")
    def xp_comma(value):
        try:
            return f"{int(value):,}"
        except (TypeError, ValueError):
            return value

    from .api import bp as api_bp
    from .auth import bp as auth_bp
    from .main import bp as main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)

    with app.app_context():
        db.create_all()
        from .seed import seed_all

        seed_all()

    return app
