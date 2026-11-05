from datetime import datetime, timedelta, timezone

import pytest

from app.extensions import db
from app.models import Artwork
from app.services import artwork_service
from app.services.artwork_service import DrawingError
from tests.conftest import (
    create_saved_draft,
    create_user,
    login,
    make_file_storage,
    make_png_bytes,
    register,
)


def test_drawing_setup_requires_login(client):
    response = client.get("/draw", follow_redirects=True)
    assert "ログイン" in response.get_data(as_text=True)


def test_start_drawing_records_deadline(app, client):
    register(client, "alice")
    login(client, "alice")
    response = client.post(
        "/draw/start", data={"duration_seconds": 30}, follow_redirects=True
    )
    assert response.status_code == 200
    with app.app_context():
        artwork = Artwork.query.first()
        assert artwork.duration_seconds == 30
        assert artwork.drawing_started_at is not None
        assert artwork.drawing_deadline > artwork.drawing_started_at
        assert artwork.status == Artwork.STATUS_DRAFT


def test_start_drawing_rejects_bad_duration(app, client):
    register(client, "alice")
    login(client, "alice")
    response = client.post(
        "/draw/start", data={"duration_seconds": 42}, follow_redirects=True
    )
    assert "10秒・30秒・1分・5分" in response.get_data(as_text=True)
    with app.app_context():
        assert Artwork.query.first() is None


def test_start_drawing_blocked_after_event_end(app, client):
    register(client, "alice")
    login(client, "alice")
    app.config["EVENT_END_AT"] = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
    response = client.post(
        "/draw/start", data={"duration_seconds": 30}, follow_redirects=True
    )
    assert "イベントは終了" in response.get_data(as_text=True)


def test_save_draft_assets_success_and_bonus(app):
    user_id = create_user(app, "alice", balance=0)
    with app.app_context():
        artwork = Artwork(artist_id=user_id, duration_seconds=30)
        db.session.add(artwork)
        db.session.commit()
        artwork, granted = artwork_service.save_draft_assets(
            artwork,
            make_file_storage("c.png"),
            [make_file_storage("l0.png"), make_file_storage("l1.png")],
            [
                {"name": "a", "visible": True, "opacity": 1.0},
                {"name": "b", "visible": False, "opacity": 0.5},
            ],
        )
        assert artwork.is_formally_saved
        assert artwork.image_path and artwork.layers_zip_path
        assert granted is True

        user = artwork.artist
        assert user.point_balance == 100

        # 再送は重複作品・重複ボーナスを防ぐ
        _, granted_again = artwork_service.save_draft_assets(
            artwork,
            make_file_storage("c.png"),
            [make_file_storage("l0.png")],
            [{"name": "a", "visible": True, "opacity": 1.0}],
        )
        assert granted_again is False
        assert user.point_balance == 100


def test_save_draft_assets_rejects_bad_png(app):
    user_id = create_user(app, "alice")
    with app.app_context():
        artwork = Artwork(artist_id=user_id, duration_seconds=30)
        db.session.add(artwork)
        db.session.commit()
        with pytest.raises(Exception):
            artwork_service.save_draft_assets(
                artwork,
                make_file_storage("c.png", size=(512, 512)),
                [make_file_storage("l0.png")],
                [{"name": "a", "visible": True, "opacity": 1.0}],
            )


def test_save_draft_assets_rejects_too_many_layers(app):
    user_id = create_user(app, "alice")
    with app.app_context():
        artwork = Artwork(artist_id=user_id, duration_seconds=30)
        db.session.add(artwork)
        db.session.commit()
        layer_files = [make_file_storage(f"l{i}.png") for i in range(11)]
        manifest = [
            {"name": f"l{i}", "visible": True, "opacity": 1.0} for i in range(11)
        ]
        with pytest.raises(Exception):
            artwork_service.save_draft_assets(
                artwork, make_file_storage("c.png"), layer_files, manifest
            )


def test_save_rejected_after_grace(app):
    user_id = create_user(app, "alice")
    with app.app_context():
        artwork = Artwork(artist_id=user_id, duration_seconds=30)
        artwork.drawing_deadline = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=120)
        db.session.add(artwork)
        db.session.commit()
        with pytest.raises(DrawingError):
            artwork_service.save_draft_assets(
                artwork,
                make_file_storage("c.png"),
                [make_file_storage("l0.png")],
                [{"name": "a", "visible": True, "opacity": 1.0}],
            )


def test_save_allowed_within_grace(app):
    user_id = create_user(app, "alice")
    with app.app_context():
        artwork = Artwork(artist_id=user_id, duration_seconds=30)
        artwork.drawing_deadline = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=30)
        db.session.add(artwork)
        db.session.commit()
        artwork, _ = artwork_service.save_draft_assets(
            artwork,
            make_file_storage("c.png"),
            [make_file_storage("l0.png")],
            [{"name": "a", "visible": True, "opacity": 1.0}],
        )
        assert artwork.is_formally_saved


def test_update_metadata(app, client):
    user_id = create_user(app, "alice")
    artwork_id = create_saved_draft(app, user_id)
    login(client, "alice")
    response = client.post(
        f"/artworks/{artwork_id}/metadata",
        data={"title": "海の絵", "description": "テスト"},
        follow_redirects=True,
    )
    assert "海の絵" in response.get_data(as_text=True)
    with app.app_context():
        from app.extensions import db as _db

        artwork = _db.session.get(Artwork, artwork_id)
        assert artwork.title == "海の絵"


def test_listing_form_requires_saved_draft(app, client):
    user_id = create_user(app, "alice")
    with app.app_context():
        artwork = Artwork(artist_id=user_id, duration_seconds=30)
        db.session.add(artwork)
        db.session.commit()
        artwork_id = artwork.id
    login(client, "alice")
    response = client.get(
        f"/artworks/{artwork_id}/listing", follow_redirects=True
    )
    assert "正式保存" in response.get_data(as_text=True)


def test_save_draft_via_http(app, client):
    register(client, "alice")
    login(client, "alice")
    client.post("/draw/start", data={"duration_seconds": 30})
    with app.app_context():
        artwork_id = Artwork.query.first().id

    png = make_png_bytes()
    layer0 = make_png_bytes()
    layer1 = make_png_bytes(color=(10, 10, 10))
    response = client.post(
        f"/draw/{artwork_id}/save",
        data={
            "manifest": (
                '[{"name":"下","visible":true,"opacity":1},'
                '{"name":"上","visible":true,"opacity":0.8}]'
            ),
            "image": (png, "artwork.png"),
            "layers": [(layer0, "layer0.png"), (layer1, "layer1.png")],
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["bonus_granted"] is True

    # 再送は already_saved
    response = client.post(
        f"/draw/{artwork_id}/save",
        data={
            "manifest": '[{"name":"a","visible":true,"opacity":1}]',
            "image": (make_png_bytes(), "artwork.png"),
            "layers": [(make_png_bytes(), "layer0.png")],
        },
        content_type="multipart/form-data",
    )
    assert response.get_json()["already_saved"] is True


def test_draft_hidden_from_others(app, client):
    user_id = create_user(app, "alice")
    artwork_id = create_saved_draft(app, user_id)
    create_user(app, "bob")
    login(client, "bob")
    response = client.get(f"/artworks/{artwork_id}")
    assert response.status_code == 404
