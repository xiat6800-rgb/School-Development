"""共通フィクスチャとテスト用ヘルパー。"""
import io
import json
import re
import struct
import zipfile

import pytest

from app import create_app
from app.extensions import db as _db


def png_bytes(size=1024):
    """検証を通す最小の PNG バイト列（署名 + IHDR）。"""
    ihdr_body = struct.pack(">II", size, size) + b"\x08\x06\x00\x00\x00"
    return (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", len(ihdr_body))
        + b"IHDR"
        + ihdr_body
        + b"\x00\x00\x00\x00"
    )


def layer_zip_bytes(layer_count=2):
    """manifest.json + レイヤーPNG を含む正しい形式の ZIP。"""
    buffer = io.BytesIO()
    manifest = {
        "format": "hew-layers-v1",
        "canvasSize": 1024,
        "layers": [
            {"name": f"レイヤー {i + 1}", "order": i, "visible": True,
             "opacity": 1, "file": f"layer_{i}.png"}
            for i in range(layer_count)
        ],
    }
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        for i in range(layer_count):
            zf.writestr(f"layer_{i}.png", png_bytes())
    return buffer.getvalue()


@pytest.fixture()
def app(tmp_path):
    application = create_app("testing")
    application.config["UPLOAD_FOLDER"] = str(tmp_path / "uploads")
    application.config["EVENT_END_UTC"] = None
    yield application
    with application.app_context():
        _db.session.remove()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    with app.app_context():
        yield _db


def register(client, username, password="pass1234"):
    response = client.post(
        "/register",
        data={"username": username, "password": password},
        follow_redirects=True,
    )
    match = re.search(r'class="code">([A-Z0-9]+)<', response.get_data(as_text=True))
    return response, (match.group(1) if match else None)


def login(client, username, password="pass1234"):
    return client.post(
        "/login", data={"username": username, "password": password},
        follow_redirects=True,
    )


def logout(client):
    return client.post("/logout", follow_redirects=True)


def start_drawing(client, duration=300):
    return client.post(
        "/artworks/draw/start", data={"duration_seconds": str(duration)},
        follow_redirects=True,
    )


def save_draft(client, artwork_id, png=None, zip_data=None):
    data = {
        "composite_png": (io.BytesIO(png if png is not None else png_bytes()), "c.png"),
        "layers_zip": (
            io.BytesIO(zip_data if zip_data is not None else layer_zip_bytes()),
            "l.zip",
        ),
    }
    return client.post(f"/artworks/{artwork_id}/save", data=data, content_type="multipart/form-data")


def draw_and_save(client):
    """ログイン中のユーザーで 描画開始 → 正式保存 を行い、作品IDを返す。"""
    start_drawing(client)
    account = client.get("/account").get_data(as_text=True)
    artwork_id = int(re.findall(r"/artworks/draft/(\d+)", account)[-1])
    result = save_draft(client, artwork_id)
    assert result.status_code == 200, result.get_data(as_text=True)
    return artwork_id


def create_saved_artwork(client, username="artist", password="pass1234"):
    """登録 → 描画開始 → 正式保存 まで進め、作品IDを返す。"""
    register(client, username, password)
    return draw_and_save(client)


def publish(client, artwork_id, title="作品", start_price=100, minutes=10, tag_ids=()):
    data = {
        "title": title,
        "description": "説明",
        "start_price": str(start_price),
        "duration_minutes": str(minutes),
        "tag_ids": [str(tag_id) for tag_id in tag_ids],
    }
    return client.post(f"/artworks/{artwork_id}/listing", data=data, follow_redirects=True)


def auction_id_from(response):
    """出品後のリダイレクト先（商品詳細）からオークションIDを取り出す。"""
    match = re.search(r"/auctions/(\d+)", response.request.path)
    return int(match.group(1)) if match else None
