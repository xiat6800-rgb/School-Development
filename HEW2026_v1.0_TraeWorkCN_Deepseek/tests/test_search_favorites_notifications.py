from datetime import timedelta

from app.extensions import db
from app.models import Artwork, ArtworkBookmark, Auction, Bookmark, Notification, Tag
from app.utils import utcnow

from tests.conftest import create_user, login


def make_listed_artwork(seller, title, tag_names, keyword_text=""):
    artwork = Artwork(
        seller_id=seller.id,
        title=title,
        description=keyword_text or None,
        image_path="dummy.png",
        status="listed",
    )
    tags = db.session.query(Tag).filter(Tag.name.in_(tag_names)).all()
    artwork.tags = tags
    db.session.add(artwork)
    db.session.flush()
    db.session.add(
        Auction(
            artwork_id=artwork.id,
            start_price=100,
            current_price=100,
            status="active",
            start_time=utcnow(),
            end_time=utcnow() + timedelta(days=1),
        )
    )
    db.session.commit()
    return artwork


def test_tag_search_uses_and_condition(client, app):
    seller = create_user("searcher", "searcher@example.com")
    both = make_listed_artwork(seller, "二つのタグ", ["動物", "風景"])
    only_one = make_listed_artwork(seller, "一つのタグ", ["動物"])

    response = client.get(f"/search/?tags={Tag.query.filter_by(name='動物').one().id}"
                          f"&tags={Tag.query.filter_by(name='風景').one().id}")
    html = response.get_data(as_text=True)
    assert "二つのタグ" in html
    assert "一つのタグ" not in html
    assert both.id != only_one.id


def test_keyword_search(client, app):
    seller = create_user("keys", "keys@example.com")
    make_listed_artwork(seller, "海の絵", ["風景"], keyword_text="青い波の記憶")
    make_listed_artwork(seller, "森の絵", ["風景"], keyword_text="緑の木々")

    html = client.get("/search/?q=波").get_data(as_text=True)
    assert "海の絵" in html
    assert "森の絵" not in html


def test_favorites_toggle_for_artwork_and_auction(client, app):
    seller = create_user("favseller", "favseller@example.com")
    buyer = create_user("favbuyer", "favbuyer@example.com", balance=1000)
    artwork = make_listed_artwork(seller, "お気に入り作品", ["動物"])
    auction = db.session.query(Auction).filter_by(artwork_id=artwork.id).one()

    login(client, "favbuyer@example.com")

    client.post(f"/favorites/artwork/{artwork.id}", data={"next": "/"}, follow_redirects=True)
    assert db.session.query(ArtworkBookmark).filter_by(user_id=buyer.id).count() == 1
    client.post(f"/favorites/artwork/{artwork.id}", data={"next": "/"}, follow_redirects=True)
    assert db.session.query(ArtworkBookmark).filter_by(user_id=buyer.id).count() == 0

    client.post(f"/favorites/auction/{auction.id}", data={"next": "/"}, follow_redirects=True)
    assert db.session.query(Bookmark).filter_by(user_id=buyer.id).count() == 1

    response = client.get("/account/?tab=favorites_auctions")
    assert response.status_code == 200
    assert "お気に入り作品" in response.get_data(as_text=True)


def test_account_tabs_render(client, app):
    create_user("tabs", "tabs@example.com")
    login(client, "tabs@example.com")
    for tab in (
        "drafts",
        "listings",
        "favorites_artworks",
        "favorites_auctions",
        "auto_bids",
        "wallet",
    ):
        response = client.get(f"/account/?tab={tab}")
        assert response.status_code == 200


def test_notification_owner_check_and_mark_read(client, app):
    owner = create_user("owner9", "owner9@example.com")
    other = create_user("other9", "other9@example.com")
    notification = Notification(
        user_id=owner.id,
        notification_type="bid_received",
        title="入札",
        message="本文",
    )
    db.session.add(notification)
    db.session.commit()

    login(client, "other9@example.com")
    assert client.post(f"/notifications/{notification.id}/read").status_code == 403

    client.post("/auth/logout")
    login(client, "owner9@example.com")
    response = client.post(
        f"/notifications/{notification.id}/read", follow_redirects=True
    )
    assert response.status_code == 200
    db.session.refresh(notification)
    assert notification.is_read is True


def test_point_pages_require_login(client):
    assert client.get("/points/bonus").status_code == 302
    assert client.get("/points/charge").status_code == 302
    assert client.get("/points/payment").status_code == 302


def test_point_pages_render_and_no_charge(client, app):
    create_user("points10", "points10@example.com", balance=1234)
    login(client, "points10@example.com")

    assert "ボーナスポイント" in client.get("/points/bonus").get_data(as_text=True)
    charge_html = client.get("/points/charge").get_data(as_text=True)
    assert "課金機能を提供していません" in charge_html
    payment_html = client.get("/points/payment").get_data(as_text=True)
    assert "決済機能を提供していません" in payment_html
