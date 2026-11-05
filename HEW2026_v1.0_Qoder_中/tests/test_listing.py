"""出品・公開のテスト（要件定義書 8章「出品」）。"""
from datetime import timedelta

import conftest
from app.models.artwork import Artwork
from app.models.auction import Auction
from app.models.user import User
from app.services import event_service

from conftest import (
    auction_id_from,
    create_saved_artwork,
    publish,
    register,
    start_drawing,
)


def test_publish_starts_auction_immediately(client, app):
    artwork_id = create_saved_artwork(client, "seller")
    response = publish(client, artwork_id, title="夕焼け", start_price=250, minutes=10)
    auction_id = auction_id_from(response)
    assert auction_id is not None
    with app.app_context():
        auction = Auction.query.get(auction_id)
        assert auction.status == "active"
        assert auction.start_price == 250
        assert auction.current_price == 250
        assert auction.end_time - auction.start_time == timedelta(minutes=10)
        artwork = Artwork.query.get(artwork_id)
        assert artwork.status == "listed"
        assert artwork.title == "夕焼け"
        # 登録1000 + 描画100 + 初出品300
        assert User.query.filter_by(username="seller").first().point_balance == 1400


def test_first_listing_bonus_only_once(client, app):
    first = create_saved_artwork(client, "seller2")
    publish(client, first)
    second = conftest.draw_and_save(client)
    publish(client, second, title="二作品目")
    with app.app_context():
        # 1000 + 100(1日目) + 300。2作目の初出品ボーナスと同日の描画ボーナスはなし
        assert User.query.filter_by(username="seller2").first().point_balance == 1400
        assert Auction.query.count() == 2


def test_publish_requires_saved_draft(client, app):
    register(client, "nosave")
    start_drawing(client)
    import re

    account = client.get("/account").get_data(as_text=True)
    artwork_id = int(re.findall(r"/artworks/draft/(\d+)", account)[0])
    response = publish(client, artwork_id)
    assert "正式保存" in response.get_data(as_text=True)
    with app.app_context():
        assert Auction.query.count() == 0


def test_publish_rejects_invalid_settings(client, app):
    artwork_id = create_saved_artwork(client, "seller3")
    response = publish(client, artwork_id, minutes=7)
    assert "開催時間" in response.get_data(as_text=True)
    response = publish(client, artwork_id, start_price=-5)
    assert "開始価格" in response.get_data(as_text=True)
    with app.app_context():
        assert Auction.query.count() == 0


def test_publish_rejected_when_event_end_too_close(client, app):
    artwork_id = create_saved_artwork(client, "seller4")
    with app.app_context():
        app.config["EVENT_END_UTC"] = event_service.utcnow() + timedelta(minutes=6)
    response = publish(client, artwork_id, minutes=10)
    assert "確保できない" in response.get_data(as_text=True)
    # 5分なら確保できる
    response = publish(client, artwork_id, minutes=5)
    assert auction_id_from(response) is not None


def test_one_auction_per_artwork(client, app):
    artwork_id = create_saved_artwork(client, "seller5")
    publish(client, artwork_id)
    response = publish(client, artwork_id, title="再出品の試み")
    # 作品は既に listed なので出品設定画面へ戻される
    assert "出品済み" in response.get_data(as_text=True)
    with app.app_context():
        assert Auction.query.count() == 1
