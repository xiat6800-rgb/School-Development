from flask import Flask, render_template

from app.config import Config
from app.extensions import csrf, db, login_manager, migrate


def create_app(config_object=None):
    app = Flask(__name__)
    app.config.from_object(config_object or Config)
    Config.init_from_env()
    if config_object is None and app.config.get("EVENT_END_AT") is None:
        app.config["EVENT_END_AT"] = Config.EVENT_END_AT

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.models import User  # noqa: F401  (user loader registration)

    from app.artworks.routes import bp as artworks_bp
    from app.auctions.routes import bp as auctions_bp
    from app.auth.routes import bp as auth_bp
    from app.favorites.routes import bp as favorites_bp
    from app.notifications.routes import bp as notifications_bp
    from app.points.routes import bp as points_bp
    from app.search.routes import bp as search_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(artworks_bp)
    app.register_blueprint(auctions_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(favorites_bp)
    app.register_blueprint(points_bp)
    app.register_blueprint(notifications_bp)

    from app.commands import register_commands

    register_commands(app)

    @app.route("/")
    def index():
        from app.services import tag_service

        artworks = tag_service.list_public_artworks()
        return render_template("index.html", artworks=artworks)

    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", message="ページが見つかりません。"), 404

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("error.html", message="権限がありません。"), 403

    return app
