import io
import json
import struct
import zipfile
import zlib

from app.models import User


def make_png(width=1024, height=1024):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + b"\xff\xff\xff" * width
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(row * height)) + chunk(b"IEND", b"")


def make_zip(png):
    buffer = io.BytesIO()
    manifest = {"canvas": {"width": 1024, "height": 1024}, "layers": [{"file": "layers/layer_01.png", "name": "layer1", "visible": True, "opacity": 1}]}
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("layers.json", json.dumps(manifest))
        archive.writestr("layers/layer_01.png", png)
    return buffer.getvalue()


def test_register_recovery_login_reset_and_save_flow(client, app):
    response = client.post("/auth/register", data={"username": "newuser", "password": "password123", "password_confirm": "password123"})
    assert response.status_code == 200
    assert "HEW-" in response.get_data(as_text=True)
    with app.app_context():
        user = User.query.filter_by(username="newuser").one()
        assert user.point_balance == 1000
        user_id = user.id
    client.post("/artworks/draw", data={"title": "保存テスト", "duration": "300"})
    with app.app_context():
        from app.models import Artwork
        artwork = Artwork.query.filter_by(artist_id=user_id).one()
        artwork_id = artwork.id
    response = client.post(f"/artworks/{artwork_id}/save", data={
        "png": (io.BytesIO(make_png()), "image.png"),
        "archive": (io.BytesIO(make_zip(make_png())), "layers.zip"),
    }, content_type="multipart/form-data")
    assert response.status_code == 200, response.get_data(as_text=True)
    with app.app_context():
        from app.models import Artwork
        from app.extensions import db
        artwork = db.session.get(Artwork, artwork_id)
        assert artwork.is_saved
        assert db.session.get(User, user_id).point_balance == 1100


def test_guest_public_pages_and_auth_required(client):
    assert client.get("/").status_code == 200
    assert client.get("/search").status_code == 200
    assert client.get("/artworks/draw").status_code == 302
    assert client.get("/account").status_code == 302
