"""描画・下書き保存のテスト（要件定義書 8章「描画」）。"""
from datetime import timedelta

import pytest

from app.models.artwork import Artwork
from app.models.user import User
from app.services import artwork_service
from app.services.artwork_service import ArtworkError

from conftest import (
    layer_zip_bytes,
    png_bytes,
    register,
    save_draft,
    start_drawing,
)


def _draft_id(client):
    import re

    account = client.get("/account").get_data(as_text=True)
    return int(re.findall(r"/artworks/draft/(\d+)", account)[0])


def test_start_drawing_records_deadline_and_rejects_change(client, app):
    register(client, "drawer")
    start_drawing(client, duration=30)
    artwork_id = _draft_id(client)
    with app.app_context():
        artwork = Artwork.query.get(artwork_id)
        assert artwork.drawing_duration_seconds == 30
        delta = artwork.drawing_deadline - artwork.drawing_started_at
        assert delta == timedelta(seconds=30)
        # 開始後は制限時間を変更できない
        with pytest.raises(ArtworkError):
            artwork_service.start_drawing_session(artwork, 300)


def test_start_drawing_rejects_invalid_duration(client):
    register(client, "drawer2")
    response = start_drawing(client, duration=45)
    assert "描画時間" in response.get_data(as_text=True)


def test_save_draft_success_and_daily_bonus_once(client, app):
    register(client, "saver")
    start_drawing(client)
    artwork_id = _draft_id(client)
    response = save_draft(client, artwork_id)
    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    with app.app_context():
        artwork = Artwork.query.get(artwork_id)
        assert artwork.is_saved
        user = User.query.filter_by(username="saver").first()
        assert user.point_balance == 1100  # 登録1000 + 描画100

    # 同じ日に2作品目を保存してもボーナスは1日1回
    start_drawing(client)
    second_id = _draft_id(client)
    save_draft(client, second_id)
    with app.app_context():
        assert User.query.filter_by(username="saver").first().point_balance == 1100


def test_save_draft_resend_does_not_duplicate(client, app):
    register(client, "resender")
    start_drawing(client)
    artwork_id = _draft_id(client)
    save_draft(client, artwork_id)
    response = save_draft(client, artwork_id)  # 再送
    assert response.status_code == 200
    with app.app_context():
        assert User.query.filter_by(username="resender").first().point_balance == 1100
        assert Artwork.query.filter_by(artist_id=1).count() == 1


def test_save_rejects_invalid_png(client, app):
    register(client, "badpng")
    start_drawing(client)
    artwork_id = _draft_id(client)
    response = save_draft(client, artwork_id, png=png_bytes(size=800))
    assert response.status_code == 400
    assert "1024" in response.get_json()["error"]
    with app.app_context():
        assert not Artwork.query.get(artwork_id).is_saved


def test_save_rejects_invalid_zip_and_rolls_back_png(client, app):
    register(client, "badzip")
    start_drawing(client)
    artwork_id = _draft_id(client)
    response = save_draft(client, artwork_id, zip_data=b"not a zip")
    assert response.status_code == 400
    with app.app_context():
        artwork = Artwork.query.get(artwork_id)
        # 片方だけ保存して正式保存成功にしない
        assert artwork.image_path is None
        assert artwork.layer_zip_path is None
        assert User.query.filter_by(username="badzip").first().point_balance == 1000


def test_save_rejects_too_many_layers(client):
    register(client, "toomany")
    start_drawing(client)
    artwork_id = _draft_id(client)
    response = save_draft(client, artwork_id, zip_data=layer_zip_bytes(layer_count=11))
    assert response.status_code == 400
    assert "10" in response.get_json()["error"]


def test_save_after_grace_period_rejected(client, app):
    register(client, "late")
    start_drawing(client, duration=10)
    artwork_id = _draft_id(client)
    with app.app_context():
        artwork = Artwork.query.get(artwork_id)
        artwork.drawing_deadline = artwork.drawing_deadline - timedelta(seconds=120)
        from app.extensions import db

        db.session.commit()
    response = save_draft(client, artwork_id)
    assert response.status_code == 400
    assert "猶予" in response.get_json()["error"]


def test_saved_artwork_cannot_be_repainted(client, app):
    register(client, "frozen")
    start_drawing(client)
    artwork_id = _draft_id(client)
    save_draft(client, artwork_id)
    with app.app_context():
        artwork = Artwork.query.get(artwork_id)
        with pytest.raises(ArtworkError):
            artwork_service.start_drawing_session(artwork, 30)


def test_author_can_download_assets(client, app):
    register(client, "downloader")
    start_drawing(client)
    artwork_id = _draft_id(client)
    save_draft(client, artwork_id)
    assert client.get(f"/artworks/{artwork_id}/download/png").status_code == 200
    assert client.get(f"/artworks/{artwork_id}/download/zip").status_code == 200
