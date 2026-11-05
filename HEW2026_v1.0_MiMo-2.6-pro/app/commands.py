"""Flask CLI コマンド。定期処理は Windows タスクスケジューラから実行する。"""

import click
from flask.cli import with_appcontext

from app.extensions import db
from app.models import Tag, User
from app.services import auction_service, point_service

INITIAL_TAGS = (
    "風景", "人物", "動物", "抽象", "ファンタジー",
    "SF", "日常", "モノクロ", "カラフル", "習作",
)


@click.command("seed-users")
@with_appcontext
def seed_users_command():
    """開発用ユーザーを準備する。"""
    samples = (
        ("alice", "alice"),
        ("bob", "bob"),
        ("carol", "carol"),
    )
    for username, password in samples:
        if User.query.filter_by(username=username).first():
            click.echo(f"skip: {username}")
            continue
        user = User(username=username, disp_name=username)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        point_service.grant_register_bonus(user)
        click.echo(f"created: {username} (password: {password})")
    db.session.commit()


@click.command("seed-tags")
@with_appcontext
def seed_tags_command():
    """初期タグを準備する。"""
    for name in INITIAL_TAGS:
        if Tag.query.filter_by(name=name).first():
            continue
        db.session.add(Tag(name=name))
        click.echo(f"tag: {name}")
    db.session.commit()


@click.command("close-auctions")
@with_appcontext
def close_auctions_command():
    """終了対象の競売を確定する。再実行でも結果は重複しない。"""
    closed = auction_service.close_expired_auctions()
    click.echo(f"closed: {len(closed)} auction(s)")


def register_commands(app):
    app.cli.add_command(seed_users_command)
    app.cli.add_command(seed_tags_command)
    app.cli.add_command(close_auctions_command)
