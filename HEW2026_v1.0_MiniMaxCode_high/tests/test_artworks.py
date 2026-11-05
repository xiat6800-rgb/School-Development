"""描画・下書き保存・出品設定のテスト（要件定義書 5.2 / 5.3）。"""

from __future__ import annotations

from datetime import timedelta

from app.extensions import db
from app.models.artwork import Artwork, DrawingSession
from app.services.artwork_service import save_draft_assets, start_drawing_session
from app.utils import utcnow


def _payload(png_data_url: str) -> dict:
    return {
        "png": png_data_url,
        "layers": [
            {"name": "レイヤー1", "visible": True, "opacity": 1.0, "data": png_data_url}
        ],
        "finished": True,
    }


def test_start_drawing_session_locks_duration(app, make_user):
    user = make_user("alice")
    artwork, session = start_drawing_session(user, 30)

    assert session.duration_seconds == 30
    assert session.deadline_at == session.started_at + timedelta(seconds=30)
    assert artwork.status == "draft"
    assert artwork.save_completed_at is None


def test_start_drawing_session_rejects_invalid_duration(app, make_user):
    from app.services.errors import ValidationError

    user = make_user("alice")
    try:
        start_drawing_session(user, 45)
    except ValidationError as error:
        assert "描画時間" in str(error)
    else:  # pragma: no cover - 例外_REQUIRED
        raise AssertionError("例外が発生しませんでした")


def test_save_draft_stores_png_and_layers(app, make_user, png_data_url):
    user = make_user("alice")
    artwork, _session = start_drawing_session(user, 60)

    save_draft_assets(user, artwork, _payload(png_data_url))
    db.session.commit()

    assert artwork.save_completed_at is not None
    assert artwork.image_path.endswith(".png")
    assert artwork.layer_archive_path.endswith(".zip")


def test_save_draft_rejects_invalid_png(app, make_user):
    from app.services.errors import ValidationError

    user = make_user("alice")
    artwork, _session = start_drawing_session(user, 60)

    try:
        save_draft_assets(user, artwork, _payload("data:image/png;base64,bm90YXBuZw=="))
    except ValidationError:
        pass
    else:  # pragma: no cover - 例外が必要な場面
        raise AssertionError("例外が発生しませんでした")


def test_save_draft_rejects_missing_layers(app, make_user, png_data_url):
    from app.services.errors import ValidationError

    user = make_user("alice")
    artwork, _session = start_drawing_session(user, 60)

    try:
        save_draft_assets(user, artwork, {"png": png_data_url, "layers": []})
    except ValidationError:
        pass
    else:  # pragma: no cover - 例外が必要な場面
        raise AssertionError("例外が発生しませんでした")


def test_save_draft_grants_draw_bonus_once_per_day(app, make_user, png_data_url):
    user = make_user("alice")
    first, _ = start_drawing_session(user, 60)
    save_draft_assets(user, first, _payload(png_data_url))
    db.session.commit()
    assert user.point_balance == 1100  # 登録 1000 + 描画 100

    second, _ = start_drawing_session(user, 60)
    save_draft_assets(user, second, _payload(png_data_url))
    db.session.commit()
    # 同じ暦日なので重複付与されない
    assert user.point_balance == 1100


def test_saved_artwork_cannot_be_saved_again(app, make_user, png_data_url):
    from app.services.errors import ConflictError

    user = make_user("alice")
    artwork, _ = start_drawing_session(user, 60)
    save_draft_assets(user, artwork, _payload(png_data_url))
    db.session.commit()

    try:
        save_draft_assets(user, artwork, _payload(png_data_url))
    except ConflictError:
        pass
    else:  # pragma: no cover - 例外が必要な場面
        raise AssertionError("例外が発生しませんでした")


def test_save_after_grace_period_is_rejected(app, make_user, png_data_url):
    from app.services.errors import BusinessRuleError

    user = make_user("alice")
    artwork, session = start_drawing_session(user, 10)
    session.deadline_at = utcnow() - timedelta(seconds=120)
    session.save_grace_until = session.deadline_at + timedelta(seconds=60)
    db.session.commit()

    try:
        save_draft_assets(user, artwork, _payload(png_data_url))
    except BusinessRuleError:
        pass
    else:  # pragma: no cover - 例外が必要な場面
        raise AssertionError("例外が発生しませんでした")


def test_other_user_cannot_open_draft_canvas(client, make_user, login):
    owner = make_user("owner")
    artwork = Artwork(
        artist_id=owner.id, title="下書き", status="draft"
    )
    db.session.add(artwork)
    db.session.commit()

    make_user("intruder")
    login("intruder")
    response = client.get(f"/artworks/{artwork.id}/canvas")
    assert response.status_code == 403


def test_publish_requires_saved_image(app, make_user, client, login):
    user = make_user("alice")
    artwork = Artwork(artist_id=user.id, title="画像なし", status="draft")
    db.session.add(artwork)
    db.session.commit()

    login("alice")
    response = client.post(
        f"/artworks/{artwork.id}/listing",
        data={"title": "画像なし", "start_price": "100", "duration_minutes": "10"},
        follow_redirects=True,
    )
    assert "出品できません" in response.get_data(as_text=True)
    assert artwork.auction is None


def test_publish_creates_active_auction(app, make_user, make_artwork, client, login):
    seller = make_user("seller")
    artwork = make_artwork(seller)
    login("seller")

    response = client.post(
        f"/artworks/{artwork.id}/listing",
        data={
            "title": "猫",
            "description": "猫の絵です",
            "start_price": "200",
            "duration_minutes": "5",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    db.session.expire_all()
    refreshed = Artwork.query.get(artwork.id)
    assert refreshed.status == "listed"
    auction = refreshed.auction
    assert auction is not None
    assert auction.status == "active"
    assert auction.start_price == 200
    assert auction.current_price == 200
    assert auction.end_time > auction.start_time
    # 初出品ボーナス 300pt が付く
    assert seller.point_balance == 1300


def test_draw_session_is_created_with_unique_artwork(app, make_user):
    user = make_user("alice")
    artwork, _ = start_drawing_session(user, 10)
    sessions = DrawingSession.query.filter_by(artwork_id=artwork.id).all()
    assert len(sessions) == 1
