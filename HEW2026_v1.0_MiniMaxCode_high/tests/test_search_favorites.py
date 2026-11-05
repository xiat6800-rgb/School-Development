"""検索・お気に入りのテスト（要件定義書 5.8）。"""

from __future__ import annotations

from app.extensions import db
from app.models.favorite import ArtworkFavorite, AuctionFavorite
from app.models.tag import Tag
from app.services import tag_service


def _tag(name: str) -> Tag:
    tag = Tag(name=name)
    db.session.add(tag)
    db.session.commit()
    return tag


def test_find_artworks_by_tags_uses_and_condition(app, make_user, make_artwork):
    artist = make_user("artist")
    cat_tag = _tag("動物")
    food_tag = _tag("食べ物")

    both = make_artwork(artist, title="猫のかわいい絵", status="listed")
    tag_service.set_artwork_tags(both, [cat_tag.id, food_tag.id])
    only_cat = make_artwork(artist, title="犬", status="listed")
    tag_service.set_artwork_tags(only_cat, [cat_tag.id])
    db.session.commit()

    results = tag_service.find_artworks_by_tags([cat_tag.id, food_tag.id])
    assert [artwork.id for artwork in results] == [both.id]

    results = tag_service.find_artworks_by_tags([cat_tag.id])
    assert {artwork.id for artwork in results} == {both.id, only_cat.id}


def test_search_page_shows_results(client, make_user, make_artwork):
    artist = make_user("artist")
    tag = _tag("動物")
    artwork = make_artwork(artist, title="猫", status="listed")
    tag_service.set_artwork_tags(artwork, [tag.id])
    db.session.commit()

    response = client.get(f"/search/?tag_ids={tag.id}")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "猫" in body
    assert "1件" in body


def test_favorite_toggle_adds_and_removes(client, make_user, make_auction, login):
    seller = make_user("seller")
    buyer = make_user("buyer")
    auction = make_auction(seller)
    login("buyer")

    client.post(f"/favorites/auctions/{auction.id}/toggle", follow_redirects=True)
    assert AuctionFavorite.query.filter_by(
        user_id=buyer.id, auction_id=auction.id
    ).count() == 1

    client.post(f"/favorites/auctions/{auction.id}/toggle", follow_redirects=True)
    assert AuctionFavorite.query.filter_by(
        user_id=buyer.id, auction_id=auction.id
    ).count() == 0


def test_artwork_favorite_toggle(client, make_user, make_artwork, login):
    artist = make_user("artist")
    buyer = make_user("buyer")
    artwork = make_artwork(artist, status="listed")
    login("buyer")

    client.post(f"/favorites/artworks/{artwork.id}/toggle", follow_redirects=True)
    assert ArtworkFavorite.query.filter_by(
        user_id=buyer.id, artwork_id=artwork.id
    ).count() == 1


def test_account_lists_favorites_separately(client, make_user, make_auction, make_artwork, login):
    seller = make_user("seller")
    buyer = make_user("buyer")
    auction = make_auction(seller)
    artwork = make_artwork(buyer, status="listed")
    login("buyer")

    client.post(f"/favorites/auctions/{auction.id}/toggle", follow_redirects=True)
    client.post(f"/favorites/artworks/{artwork.id}/toggle", follow_redirects=True)

    response = client.get("/account/?tab=favorites")
    body = response.get_data(as_text=True)
    assert "作品のお気に入り" in body
    assert "オークションのお気に入り" in body


def test_draft_artwork_is_not_favoritable(client, make_user, make_artwork, login):
    artist = make_user("artist")
    buyer = make_user("buyer")
    artwork = make_artwork(artist, status="draft")
    login("buyer")

    response = client.post(
        f"/favorites/artworks/{artwork.id}/toggle", follow_redirects=True
    )
    assert "公開中の作品だけ" in response.get_data(as_text=True)
    assert ArtworkFavorite.query.count() == 0
