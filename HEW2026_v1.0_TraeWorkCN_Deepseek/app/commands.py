"""Flask CLI コマンド（開発用データ準備とオークション終了処理）。"""
import os
import secrets
import struct
import uuid
import zlib
from datetime import timedelta

import click
from flask import current_app
from sqlalchemy import select

from app.extensions import db
from app.models import Artwork, Auction, Tag, User
from app.services.auction_service import close_auctions as run_close_auctions
from app.services.bonus_service import grant_signup_bonus
from app.services.tag_service import seed_initial_tags
from app.utils import utcnow


def register_commands(app):
    for command in (init_db, seed_tags, seed_users, seed_demo, close_auctions):
        app.cli.add_command(command)


@click.command("init-db")
def init_db():
    """モデル定義からテーブルを作成する（開発用の簡易セットアップ）。"""
    db.create_all()
    click.echo("テーブルを作成しました。本番のスキーマ管理は Flask-Migrate を使用してください。")


@click.command("seed-tags")
def seed_tags():
    """初期タグを登録する。"""
    created = seed_initial_tags()
    click.echo(f"初期タグを登録しました（新規 {created} 件）。")


@click.command("seed-users")
@click.option("--password", default=None, help="開発用アカウントのパスワード。省略時は自動生成。")
def seed_users(password):
    """開発用アカウント sample1〜3 を作成する。"""
    raw_password = password or secrets.token_urlsafe(9)
    created = []

    for username in ("sample1", "sample2", "sample3"):
        exists = db.session.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none()
        if exists is not None:
            continue

        user = User(
            username=username,
            email=f"{username}@example.com",
            disp_name="",
            role="user",
        )
        user.set_password(raw_password)
        db.session.add(user)
        db.session.flush()
        user.disp_name = f"user{user.id}"
        grant_signup_bonus(user)
        created.append(username)

    db.session.commit()
    if created:
        click.echo(f"作成: {', '.join(created)} / パスワード: {raw_password}")
    else:
        click.echo("開発用アカウントはすでに存在します。")


def _demo_png(width=480, height=360, offset=0):
    """デモ用の抽象画 PNG を生成する（外部画像に依存しない）。"""
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            ratio_x = x / width
            ratio_y = y / height
            circle = ((x - width * (0.3 + offset * 0.1)) ** 2 + (y - height * 0.45) ** 2) ** 0.5
            glow = max(0.0, 1.0 - circle / (width * 0.45))
            r = int(30 + 150 * ratio_x + 60 * glow)
            g = int(50 + 90 * ratio_y + 40 * glow)
            b = int(90 + 100 * (1 - ratio_x) + 50 * glow)
            row += bytes((min(r, 255), min(g, 255), min(b, 255)))
        rows.append(bytes(row))

    raw = b"".join(rows)

    def chunk(tag, data):
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


@click.command("seed-demo")
def seed_demo():
    """デモ用の作品とオークションを作成する（先に seed-users / seed-tags を実行）。"""
    seller = db.session.execute(
        select(User).where(User.username == "sample1")
    ).scalar_one_or_none()
    if seller is None:
        click.echo("先に `flask seed-users` を実行してください。")
        raise click.exceptions.Exit(1)

    existing = db.session.execute(
        select(Artwork).where(Artwork.title.like("デモ作品%"))
    ).scalars().first()
    if existing is not None:
        click.echo("デモ作品はすでに存在します。")
        return

    tags = db.session.execute(select(Tag).order_by(Tag.id.asc())).scalars().all()
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)

    titles = [
        ("デモ作品 1 夜明けの記憶", 300, 1),
        ("デモ作品 2 静かな海", 500, 2),
        ("デモ作品 3 光の庭", 800, 3),
    ]
    for index, (title, start_price, days) in enumerate(titles):
        filename = f"{uuid.uuid4().hex}.png"
        with open(os.path.join(upload_folder, filename), "wb") as handle:
            handle.write(_demo_png(offset=index))
        artwork = Artwork(
            seller_id=seller.id,
            title=title,
            description="デモ用に生成した抽象画です。入札の動作確認に利用できます。",
            image_path=filename,
            status="listed",
        )
        if tags:
            artwork.tags = [tags[index % len(tags)], tags[(index + 2) % len(tags)]]
        db.session.add(artwork)
        db.session.flush()

        db.session.add(
            Auction(
                artwork_id=artwork.id,
                start_price=start_price,
                current_price=start_price,
                status="active",
                start_time=utcnow(),
                end_time=utcnow().replace(microsecond=0) + timedelta(days=days),
            )
        )

    db.session.commit()
    click.echo("デモ作品とオークションを作成しました。")


@click.command("close-auctions")
def close_auctions():
    """終了日時を過ぎたオークションの落札を確定する（タスクスケジューラから定期実行）。"""
    closed = run_close_auctions()
    click.echo(f"終了処理を行ったオークション: {len(closed)} 件")
