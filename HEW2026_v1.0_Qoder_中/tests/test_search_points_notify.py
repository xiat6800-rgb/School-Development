"""検索・お気に入り・通知・ポイント画面のテスト（要件定義書 8章）。"""
import re

from app.extensions import db
from app.models.tag import Tag
from app.services import tag_service

from conftest import (
    auction_id_from,
    create_saved_artwork,
    draw_and_save,
    login,
    logout,
    publish,
    register,
)


def _seed_tags(app):
    with app.app_context():
        tag_service.seed_default_tags()
        return {tag.name: tag.id for tag in Tag.query.all()}


def test_tag_and_search(app, client):
    tag_ids = _seed_tags(app)
    artwork_id = create_saved_artwork(client, "artist1")
    publish(client, artwork_id, title="猫の絵",
           tag_ids=[tag_ids["動物"], tag_ids["カラー"]])
    second = draw_and_save(client)
    publish(client, second, title="風景画", tag_ids=[tag_ids["風景"]])

    # 単一タグ
    response = client.get(f"/search?tag_ids={tag_ids['動物']}")
    body = response.get_data(as_text=True)
    assert "猫の絵" in body and "風景画" not in body

    # AND 条件: 両方持つ作品だけ
    response = client.get(
        f"/search?tag_ids={tag_ids['動物']}&tag_ids={tag_ids['カラー']}"
    )
    assert "猫の絵" in response.get_data(as_text=True)
    response = client.get(
        f"/search?tag_ids={tag_ids['動物']}&tag_ids={tag_ids['風景']}"
    )
    body = response.get_data(as_text=True)
    assert "猫の絵" not in body and "風景画" not in body


def test_duplicate_tag_assignment_prevented(app, client):
    tag_ids = _seed_tags(app)
    artwork_id = create_saved_artwork(client, "artist2")
    publish(client, artwork_id, tag_ids=[tag_ids["動物"], tag_ids["動物"]])
    with app.app_context():
        from app.models.artwork import Artwork

        artwork = Artwork.query.get(artwork_id)
        assert len(artwork.tags) == 1


def test_artwork_and_auction_favorites_separately(app, client):
    artwork_id = create_saved_artwork(client, "artist3")
    auction_id = auction_id_from(publish(client, artwork_id))
    logout(client)
    register(client, "fan")

    client.post(f"/favorites/artworks/{artwork_id}/add", follow_redirects=True)
    client.post(f"/favorites/auctions/{auction_id}/add", follow_redirects=True)
    # 重複登録は一意制約で防止（エラーにならない）
    client.post(f"/favorites/artworks/{artwork_id}/add", follow_redirects=True)

    account = client.get("/account").get_data(as_text=True)
    assert "作品のお気に入り" in account
    assert "オークションのお気に入り" in account
    assert account.count(f"/auctions/{auction_id}") >= 1

    client.post(f"/favorites/artworks/{artwork_id}/remove", follow_redirects=True)
    with app.app_context():
        from app.models.favorite import ArtworkFavorite, AuctionFavorite

        assert ArtworkFavorite.query.count() == 0
        assert AuctionFavorite.query.count() == 1


def test_favorite_requires_public_artwork(app, client):
    artwork_id = create_saved_artwork(client, "artist4")  # 未出品の下書き
    logout(client)
    register(client, "stalker")
    assert client.post(
        f"/favorites/artworks/{artwork_id}/add"
    ).status_code == 404


def test_notifications_created_and_read(app, client):
    artwork_id = create_saved_artwork(client, "artist5")
    auction_id = auction_id_from(publish(client, artwork_id))
    logout(client)
    register(client, "bidder")
    client.post(
        f"/auctions/{auction_id}/bid", data={"amount": "150"},
        follow_redirects=True,
    )
    # 出品者への入札受付通知
    logout(client)
    login(client, "artist5")
    body = client.get("/notifications").get_data(as_text=True)
    assert "入札がありました" in body
    notification_id = int(re.search(r"/notifications/(\d+)/read", body).group(1))
    response = client.post(f"/notifications/{notification_id}/read", follow_redirects=True)
    # 関連する商品詳細へ移動できる
    assert response.request.path == f"/auctions/{auction_id}"
    with app.app_context():
        from app.models.notification import Notification

        assert Notification.query.get(notification_id).is_read


def test_notification_owner_only(app, client):
    artwork_id = create_saved_artwork(client, "artist6")
    auction_id = auction_id_from(publish(client, artwork_id))
    logout(client)
    register(client, "bidder")
    client.post(
        f"/auctions/{auction_id}/bid", data={"amount": "120"},
        follow_redirects=True,
    )
    with app.app_context():
        from app.models.notification import Notification

        notification = Notification.query.filter_by(notification_type="bid_received").first()
        notification_id = notification.id
    # 他人の通知は既読にできない
    assert client.post(f"/notifications/{notification_id}/read").status_code == 403


def test_bonus_and_charge_pages(app, client):
    register(client, "viewer")
    body = client.get("/points/bonus").get_data(as_text=True)
    assert "1,000pt" in body or "1000pt" in body
    assert "自動付与" in body
    charge = client.get("/points/charge").get_data(as_text=True)
    # Ver0.5 では課金機能が未提供であることを明示する
    assert "課金機能を提供していません" in charge
    assert client.get("/points/payment").status_code == 200


def test_guest_can_view_and_search(app, client):
    tag_ids = _seed_tags(app)
    artwork_id = create_saved_artwork(client, "artist7")
    publish(client, artwork_id, title="公開作品", tag_ids=[tag_ids["風景"]])
    logout(client)
    assert client.get("/").status_code == 200
    body = client.get(f"/search?tag_ids={tag_ids['風景']}").get_data(as_text=True)
    assert "公開作品" in body
    # ゲストは入札できない
    response = client.post("/auctions/1/bid", data={"amount": "999"}, follow_redirects=True)
    assert "ログイン" in response.get_data(as_text=True)
