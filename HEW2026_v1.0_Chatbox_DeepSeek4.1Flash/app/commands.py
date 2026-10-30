"""開発・定期実行用の Flask CLI コマンド。"""

import click
from flask.cli import with_appcontext

from .constants import BONUS_REGISTRATION, ROLE_ADMIN
from .extensions import db
from .models import Tag, User
from .services import auction_service, point_service

DEFAULT_TAGS = (
    "free",
    "乗り物",
    "動物",
    "昆虫",
    "植物",
    "食べ物",
    "キャラクター",
    "random",
)


@click.command("seed-tags")
@with_appcontext
def seed_tags_command():
    """初期タグを登録する。"""
    created = 0
    for name in DEFAULT_TAGS:
        exists = db.session.scalar(db.select(Tag).where(Tag.name == name))
        if exists is None:
            db.session.add(Tag(name=name))
            created += 1
    db.session.commit()
    click.echo(f"タグを準備しました（新規 {created} 件）。")


@click.command("seed-users")
@with_appcontext
def seed_users_command():
    """開発用ユーザー（出品者 1 名・入札者 2 名・管理者 1 名）を準備する。"""
    seeds = (
        ("seller", "出品者テスト", 5000, "user"),
        ("bidder1", "入札者テスト1", 5000, "user"),
        ("bidder2", "入札者テスト2", 5000, "user"),
        ("admin", "管理者テスト", 5000, ROLE_ADMIN),
    )
    created = 0
    for username, disp_name, points, role in seeds:
        user = db.session.scalar(db.select(User).where(User.username == username))
        if user is not None:
            click.echo(f"{username} は既に存在します。")
            continue
        user = User(username=username, disp_name=disp_name, role=role)
        user.set_password("hew2026demo")
        user.issue_recovery_code()
        db.session.add(user)
        db.session.flush()
        point_service.grant_bonus_points(user, BONUS_REGISTRATION)
        if user.point_balance < points:
            point_service.add_points(
                user,
                points - user.point_balance,
                "charge",
                memo="開発用の初期ポイント",
            )
        created += 1
    db.session.commit()
    click.echo(f"開発用ユーザーを準備しました（新規 {created} 件 / パスワード hew2026demo）。")


@click.command("close-auctions")
@with_appcontext
def close_auctions_command():
    """終了日時を過ぎた競売を確定する（定期実行する）。"""
    closed = auction_service.close_expired_auctions()
    click.echo(f"確定処理を実行しました（対象 {closed} 件）。")


def register_commands(app):
    """アプリへ CLI コマンドを登録する。"""
    app.cli.add_command(seed_tags_command)
    app.cli.add_command(seed_users_command)
    app.cli.add_command(close_auctions_command)
