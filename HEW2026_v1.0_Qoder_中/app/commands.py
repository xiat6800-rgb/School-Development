"""Flask CLI コマンド。定期処理は Windows タスクスケジューラから実行する。"""
import click
from flask.cli import with_appcontext

from .extensions import db
from .models.user import User
from .services import auction_service, tag_service


def register_commands(app):
    app.cli.add_command(seed_users_command)
    app.cli.add_command(seed_tags_command)
    app.cli.add_command(close_auctions_command)


@click.command("seed-users")
@with_appcontext
def seed_users_command():
    """開発用ユーザーを準備する。"""
    created = []
    for name in ("devuser", "bidder1", "bidder2"):
        if not User.query.filter_by(username=name).first():
            user = User(username=name, disp_name=name)
            user.set_password("devpass123")
            db.session.add(user)
            db.session.flush()
            user.disp_name = f"user{user.id}"
            created.append(name)
    db.session.commit()
    admin = User.query.filter_by(username="admin").first()
    if admin is None:
        admin = User(username="admin", disp_name="admin", role="admin")
        admin.set_password("adminpass123")
        db.session.add(admin)
        db.session.commit()
        created.append("admin")
    click.echo(f"prepared: {', '.join(created) if created else '(none)'}")


@click.command("seed-tags")
@with_appcontext
def seed_tags_command():
    """初期タグを準備する。"""
    click.echo(f"created tags: {tag_service.seed_default_tags()}")


@click.command("close-auctions")
@with_appcontext
def close_auctions_command():
    """終了対象の競売を確定する（再実行しても二重処理しない）。"""
    count = auction_service.close_expired_auctions()
    click.echo(f"closed auctions: {count}")
