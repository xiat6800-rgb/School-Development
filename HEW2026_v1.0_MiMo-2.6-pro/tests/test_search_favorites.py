from app.extensions import db
from app.models import Artwork, ArtworkBookmark, ArtworkTag, Bookmark, Tag
from app.services import tag_service
from tests.conftest import create_auction, create_saved_draft, create_user, login


def _seed_tags(app):
    with app.app_context():
        names = ["風景", "人物", "動物"]
        tags = []
        for name in names:
            tag = Tag(name=name)
            db.session.add(tag)
            tags.append(tag)
        db.session.commit()
        return [t.id for t in tags]


def test_tag_search_and_condition(app):
    seller_id = create_user(app, "seller")
    tag_ids = _seed_tags(app)
    artwork_a = create_saved_draft(app, seller_id, title="A")
    artwork_b = create_saved_draft(app, seller_id, title="B")
    create_auction(app, artwork_a, seller_id)
    create_auction(app, artwork_b, seller_id)

    with app.app_context():
        art_a = db.session.get(Artwork, artwork_a)
        art_b = db.session.get(Artwork, artwork_b)
        tag_service.set_artwork_tags(art_a, [tag_ids[0], tag_ids[1]])
        tag_service.set_artwork_tags(art_b, [tag_ids[0], tag_ids[2]])
        db.session.commit()

        # AND 条件：風景+人物 → A のみ
        results = tag_service.find_artworks_by_tags([tag_ids[0], tag_ids[1]])
        assert [a.id for a in results] == [artwork_a]

        # 風景のみ → A と B
        results = tag_service.find_artworks_by_tags([tag_ids[0]])
        assert sorted(a.id for a in results) == sorted([artwork_a, artwork_b])

        # 一致なし
        results = tag_service.find_artworks_by_tags([tag_ids[1], tag_ids[2]])
        assert results == []


def test_set_artwork_tags_prevents_duplicates(app):
    seller_id = create_user(app, "seller")
    tag_ids = _seed_tags(app)
    artwork_id = create_saved_draft(app, seller_id)
    with app.app_context():
        artwork = db.session.get(Artwork, artwork_id)
        tag_service.set_artwork_tags(artwork, [tag_ids[0], tag_ids[0]])
        db.session.commit()
        links = ArtworkTag.query.filter_by(artwork_id=artwork_id).all()
        assert len(links) == 1


def test_artwork_favorites_add_remove(app, client):
    seller_id = create_user(app, "seller")
    artwork_id = create_saved_draft(app, seller_id)
    create_auction(app, artwork_id, seller_id)
    create_user(app, "bob")
    login(client, "bob")

    response = client.post(
        f"/artworks/{artwork_id}/favorite/add", follow_redirects=True
    )
    assert "登録しました" in response.get_data(as_text=True)
    with app.app_context():
        assert ArtworkBookmark.query.filter_by(artwork_id=artwork_id).count() == 1
        # 重複登録は増えない
    client.post(f"/artworks/{artwork_id}/favorite/add", follow_redirects=True)
    with app.app_context():
        assert ArtworkBookmark.query.filter_by(artwork_id=artwork_id).count() == 1

    response = client.post(
        f"/artworks/{artwork_id}/favorite/remove", follow_redirects=True
    )
    assert "解除しました" in response.get_data(as_text=True)
    with app.app_context():
        assert ArtworkBookmark.query.filter_by(artwork_id=artwork_id).count() == 0


def test_auction_favorites_and_list_pages(app, client):
    seller_id = create_user(app, "seller")
    artwork_id = create_saved_draft(app, seller_id)
    auction_id = create_auction(app, artwork_id, seller_id)
    create_user(app, "bob")
    login(client, "bob")

    client.post(f"/auctions/{auction_id}/favorite/add", follow_redirects=True)
    with app.app_context():
        assert Bookmark.query.filter_by(auction_id=auction_id).count() == 1

    response = client.get("/account/favorites/auctions")
    assert response.status_code == 200
    assert "オークション" in response.get_data(as_text=True)

    response = client.get("/account/favorites/artworks")
    assert response.status_code == 200

    response = client.post(
        f"/auctions/{auction_id}/favorite/remove", follow_redirects=True
    )
    assert "解除しました" in response.get_data(as_text=True)
