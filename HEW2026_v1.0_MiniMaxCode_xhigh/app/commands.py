"""Flask CLI コマンド。

- ``init-db``      : テーブルを直接作る（ベースライン確定後は使わない）
- ``seed-tags``    : 初期タグを登録する
- ``seed-users``   : 開発用ユーザーを登録する
- ``seed-demo``    : デモ作品とオークションを作る
- ``close-auctions``: 終了日時を過ぎたオークションを確定する
"""

from __future__ import annotations

import click
from flask import Flask
from flask.cli import with_appcontext

from app.extensions import db

# memo.md のタグ案
DEFAULT_TAGS = (
    "free",
    "乗り物",
    "動物",
    "昆虫",
    "植物",
    "食べ物",
    "キャラクター",
)

DEMO_TITLES = ("猫のかわいい絵", "船のイラスト", "飛行機のイラスト")


def register_commands(app: Flask) -> None:
    """CLI コマンドをアプリへ登録する。"""
    app.cli.add_command(init_db)
    app.cli.add_command(seed_tags)
    app.cli.add_command(seed_users)
    app.cli.add_command(seed_demo)
    app.cli.add_command(close_auctions)


@click.command("init-db")
@with_appcontext
def init_db() -> None:
    """モデル定義からテーブルを作成する（開発用）。

    ベースラインのマイグレーションを適用した後は使わないでください。
    ``flask db migrate`` が全テーブルを CREATE する差分を作ってしまいます。
    """
    db.create_all()
    click.echo("テーブルを作成しました。")


@click.command("seed-tags")
@with_appcontext
def seed_tags() -> None:
    """初期タグを登録する。"""
    from app.models.tag import Tag

    created = 0
    for name in DEFAULT_TAGS:
        if Tag.query.filter_by(name=name).first() is None:
            db.session.add(Tag(name=name))
            created += 1
    db.session.commit()
    click.echo(f"タグを登録しました（新規 {created} 件 / 合計 {Tag.query.count()} 件）。")


@click.command("seed-users")
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
@click.option("--points", default=10000, show_default=True, help="初期ポイント")
@with_appcontext
def seed_users(password: str, points: int) -> None:
    """開発用ユーザー（sample1〜sample3）を作成する。"""
    from app.models.user import User
    from app.services.auth_service import generate_recovery_code

    created = []
    for index in range(1, 4):
        username = f"sample{index}"
        user = User.query.filter_by(username=username).first()
        if user is None:
            user = User(username=username, disp_name=f"user{index}", point_balance=0)
            user.set_password(password)
            code = generate_recovery_code()
            user.set_recovery_code(code)
            db.session.add(user)
            db.session.flush()
            user.point_balance = points
            created.append((username, code))
    db.session.commit()

    for username, code in created:
        click.echo(f"{username} を作成しました。復旧コード: {code}")
    if not created:
        click.echo("sample1〜sample3 はすでに存在します。")


@click.command("seed-demo")
@with_appcontext
def seed_demo() -> None:
    """デモ作品（3点）と開催中のオークションを作成する。"""
    from app.models.artwork import Artwork
    from app.models.user import User
    from app.services import auction_service
    from app.services.image_service import create_solid_png, save_png
    from app.services.layer_service import save_layer_archive

    seller = User.query.filter_by(username="sample1").first()
    if seller is None:
        click.echo("sample1 がいません。先に seed-users を実行してください。")
        return

    titles = DEMO_TITLES
    created = 0
    for index, title in enumerate(titles):
        artwork = Artwork.query.filter_by(artist_id=seller.id, title=title).first()
        if artwork is None:
            artwork = Artwork(artist_id=seller.id, title=title, description="デモ用の作品です。")
            db.session.add(artwork)
            db.session.flush()

            png = create_solid_png(512, 512, (210 - index * 20, 230, 250 - index * 20))
            artwork.image_path = save_png(png)
            artwork.layer_archive_path = save_layer_archive(
                [
                    {
                        "name": "レイヤー1",
                        "visible": True,
                        "opacity": 1.0,
                        "data": png,
                    }
                ]
            )
            artwork.save_completed_at = db.func.now()
            db.session.flush()

            auction_service.create_auction(
                seller,
                artwork,
                title,
                artwork.description or "",
                [],
                100 * (index + 1),
                10,
            )
            created += 1
    db.session.commit()
    click.echo(f"デモ作品とオークションを作成しました（新規 {created} 件）。")


@click.command("close-auctions")
@with_appcontext
def close_auctions() -> None:
    """終了日時を過ぎたオークションを確定する（定期実行用）。"""
    from app.services import auction_service

    closed = auction_service.close_expired_auctions()
    db.session.commit()
    click.echo(f"{len(closed)} 件のオークションを確定しました。")
