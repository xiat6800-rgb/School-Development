from app.extensions import db
from app.models import Artwork, User

from tests.conftest import SMALL_PNG, login


def test_register_grants_bonus_and_sets_display_name(client, app):
    response = client.post(
        "/auth/register",
        data={
            "username": "alice",
            "email": "Alice@Example.com",
            "password": "password123",
            "confirm": "password123",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    user = db.session.query(User).filter_by(username="alice").first()
    assert user is not None
    assert user.email == "alice@example.com"
    assert user.check_password("password123")
    assert user.disp_name == f"user{user.id}"
    assert user.point_balance == app.config["BONUS_SIGNUP_POINTS"]


def test_register_rejects_duplicate_username_and_email(client, app):
    client.post(
        "/auth/register",
        data={
            "username": "alice",
            "email": "alice@example.com",
            "password": "password123",
            "confirm": "password123",
        },
    )
    client.post("/auth/logout")
    response = client.post(
        "/auth/register",
        data={
            "username": "alice",
            "email": "other@example.com",
            "password": "password123",
            "confirm": "password123",
        },
        follow_redirects=True,
    )
    assert "使用されています" in response.get_data(as_text=True)


def test_login_and_logout(client, app):
    client.post(
        "/auth/register",
        data={
            "username": "bob",
            "email": "bob@example.com",
            "password": "password123",
            "confirm": "password123",
        },
    )
    client.post("/auth/logout")

    assert "正しくありません" in login(client, "bob@example.com", "wrongpass").get_data(
        as_text=True
    )
    assert login(client, "bob@example.com").status_code == 200


def test_draw_save_creates_draft_and_image_is_owner_only(client, app):
    client.post(
        "/auth/register",
        data={
            "username": "drawer",
            "email": "drawer@example.com",
            "password": "password123",
            "confirm": "password123",
        },
    )
    user = db.session.query(User).filter_by(username="drawer").first()
    balance_after_register = user.point_balance

    response = client.post(
        "/artworks/draw", data={"image_data": SMALL_PNG}, follow_redirects=True
    )
    assert response.status_code == 200

    artwork = db.session.query(Artwork).filter_by(seller_id=user.id).first()
    assert artwork is not None
    assert artwork.status == "draft"
    assert artwork.image_path.endswith(".png")

    assert client.get(f"/artworks/{artwork.id}/image").status_code == 200

    client.post("/auth/logout")
    assert client.get(f"/artworks/{artwork.id}/image").status_code == 403

    db.session.refresh(user)
    assert user.point_balance == balance_after_register + app.config["BONUS_DRAW_POINTS"]


def test_draw_rejects_non_png_payload(client, app):
    client.post(
        "/auth/register",
        data={
            "username": "badpng",
            "email": "badpng@example.com",
            "password": "password123",
            "confirm": "password123",
        },
    )
    response = client.post(
        "/artworks/draw",
        data={"image_data": "data:image/png;base64,bm90LWEtcG5n"},
        follow_redirects=True,
    )
    assert "PNG" in response.get_data(as_text=True)
    assert db.session.query(Artwork).count() == 0


def test_guest_cannot_open_draw_page(client):
    response = client.get("/artworks/draw")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_other_user_cannot_view_draft_image(client, app):
    from tests.conftest import create_user

    owner = create_user("owner", "owner@example.com")
    create_user("other", "other@example.com")
    artwork = Artwork(
        seller_id=owner.id, title="下書き", image_path="dummy.png", status="draft"
    )
    db.session.add(artwork)
    db.session.commit()

    login(client, "other@example.com")
    assert client.get(f"/artworks/{artwork.id}/image").status_code == 403
