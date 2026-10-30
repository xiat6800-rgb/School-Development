import io
import json
import math
import struct
import zipfile
import zlib
from datetime import timedelta

import click
from flask import current_app
from flask.cli import with_appcontext

from app.constants import INITIAL_TAGS
from app.extensions import db
from app.models import Artwork, LiveStream, Tag, User
from app.services.artwork_service import create_draft
from app.services.auction_service import close_expired_auctions, create_auction
from app.services.auth_service import generate_recovery_code
from app.services.comment_service import purge_expired_comment_bodies
from app.services.image_service import save_png_and_archive
from app.services.point_service import grant_bonus_points
from app.services.stream_service import close_stale_streams
from app.utils import utcnow


def _chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def _demo_png(variant):
    """依存ライブラリなしで1024pxのデモPNGを生成する。"""
    width = height = 1024
    rows = []
    palettes = (
        ((239, 241, 232), (38, 75, 196), (235, 91, 67)),
        ((228, 239, 244), (23, 48, 71), (239, 190, 55)),
        ((244, 232, 237), (92, 55, 132), (39, 133, 114)),
    )
    bg, primary, accent = palettes[variant % 3]
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            color = bg
            if variant == 0:
                if (x - 390) ** 2 + (y - 450) ** 2 < 280 ** 2:
                    color = primary
                if (x - 670) ** 2 + (y - 650) ** 2 < 190 ** 2:
                    color = accent
                if 80 < x < 945 and 160 < y < 184:
                    color = primary
            elif variant == 1:
                if ((x + y) // 90) % 2 == 0 and 170 < x < 850 and 170 < y < 850:
                    color = primary
                if abs(x - y) < 45 or abs((1023 - x) - y) < 45:
                    color = accent
            else:
                wave = 500 + math.sin(x / 75) * 150
                if abs(y - wave) < 90:
                    color = primary
                if (x - 700) ** 2 + (y - 300) ** 2 < 150 ** 2:
                    color = accent
            row.extend(color)
        rows.append(bytes(row))
    raw = b"".join(rows)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(raw, 7)) + _chunk(b"IEND", b"")


def _demo_zip(png_data, title):
    buffer = io.BytesIO()
    manifest = {"version": 1, "canvas": {"width": 1024, "height": 1024}, "layers": [{
        "file": "layers/layer_01.png", "name": title, "visible": True, "opacity": 1.0,
    }]}
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("layers.json", json.dumps(manifest, ensure_ascii=False))
        archive.writestr("layers/layer_01.png", png_data)
    return buffer.getvalue()


@click.command("init-db")
@with_appcontext
def init_db_command():
    db.create_all()
    click.echo("DBテーブルを作成しました。")


@click.command("seed-tags")
@with_appcontext
def seed_tags_command():
    created = 0
    for name in INITIAL_TAGS:
        if not Tag.query.filter_by(name=name).first():
            db.session.add(Tag(name=name))
            created += 1
    db.session.commit()
    click.echo(f"初期タグ: {created}件を追加しました。")


@click.command("seed-demo")
@click.option("--password", prompt=True, hide_input=True, help="デモ全アカウントのローカル用パスワード")
@with_appcontext
def seed_demo_command(password):
    if len(password) < 8:
        raise click.ClickException("パスワードは8文字以上にしてください。")
    if User.query.filter_by(username="sample1").first():
        raise click.ClickException("デモデータはすでに存在します。")
    db.create_all()
    for name in INITIAL_TAGS:
        if not Tag.query.filter_by(name=name).first():
            db.session.add(Tag(name=name))
    users = []
    for username, role in (("sample1", "user"), ("sample2", "user"), ("sample3", "user"), ("admin", "admin")):
        code = generate_recovery_code()
        user = User(username=username, display_name=username, role=role)
        user.set_password(password)
        user.set_recovery_code(code)
        db.session.add(user)
        db.session.flush()
        grant_bonus_points(user, "register")
        users.append(user)
        click.echo(f"{username} recovery: {code}")
    db.session.flush()
    now = utcnow()
    samples = (
        ("青い窓と夕食", "10分で描いた色の記録。", 120, 20, (0, 3)),
        ("交差点のリズム", "線と余白だけの小さな実験。", 50, 15, (2, 6)),
        ("波の上の惑星", "曲線と円が出会う場所。", 0, 10, (0, 2)),
    )
    for index, (title, description, price, minutes, tag_indexes) in enumerate(samples):
        artwork = create_draft(users[0], 300, title, now=now)
        artwork.drawing_started_at = now - timedelta(minutes=6)
        artwork.drawing_ends_at = now - timedelta(minutes=1)
        artwork.finished_at = now - timedelta(minutes=2)
        artwork.description = description
        png = _demo_png(index)
        archive = _demo_zip(png, title)
        artwork.image_path, artwork.archive_path = save_png_and_archive(png, archive)
        artwork.saved_at = now - timedelta(minutes=2)
        artwork.tags = [Tag.query.filter_by(name=INITIAL_TAGS[i]).first() for i in tag_indexes]
        db.session.flush()
        create_auction(artwork, price, minutes, now=now)
    db.session.commit()
    click.echo("デモユーザー・作品3点を作成しました。sample1が作者、sample2/3が入札者です。")


@click.command("close-auctions")
@with_appcontext
def close_auctions_command():
    count = close_expired_auctions()
    db.session.commit()
    click.echo(f"終了確定: {count}件")


@click.command("close-stale-streams")
@with_appcontext
def close_stale_streams_command():
    result = close_stale_streams()
    db.session.commit()
    click.echo(f"中断: {result['paused']}件 / 終了: {result['ended']}件")


@click.command("purge-comment-bodies")
@with_appcontext
def purge_comment_bodies_command():
    count = purge_expired_comment_bodies()
    db.session.commit()
    click.echo(f"本文消去: {count}件（監査記録は保持）")


def register_commands(app):
    for command in (
        init_db_command, seed_tags_command, seed_demo_command,
        close_auctions_command, close_stale_streams_command,
        purge_comment_bodies_command,
    ):
        app.cli.add_command(command)
