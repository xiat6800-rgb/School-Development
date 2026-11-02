"""通知・ボーナス・補助画面のテスト（要件定義書 5.7 / 5.9）。"""

from __future__ import annotations

from app.extensions import db
from app.models.notification import Notification
from app.services import auction_service


def test_bid_creates_notifications_for_seller_and_previous_bidder(
    app, make_user, make_auction
):
    seller = make_user("seller")
    first = make_user("first", points=1000)
    second = make_user("second", points=1000)
    auction = make_auction(seller, start_price=100)

    auction_service.place_bid(auction.id, first, 200)
    db.session.commit()
    auction_service.place_bid(auction.id, second, 300)
    db.session.commit()

    seller_notice = Notification.query.filter_by(
        user_id=seller.id, notification_type="bid_received"
    ).count()
    assert seller_notice == 2

    price_notice = Notification.query.filter_by(
        user_id=first.id, notification_type="price_updated"
    ).count()
    assert price_notice == 1


def test_auction_won_notification_sent_to_bidder_and_seller(
    app, make_user, make_auction
):
    seller = make_user("seller")
    bidder = make_user("bidder", points=1000)
    auction = make_auction(seller, start_price=100)

    auction_service.place_bid(auction.id, bidder, 300)
    db.session.commit()
    auction_service.close_auction(auction.id)
    db.session.commit()

    assert (
        Notification.query.filter_by(
            user_id=bidder.id, notification_type="auction_won"
        ).count()
        == 1
    )
    assert (
        Notification.query.filter_by(
            user_id=seller.id, notification_type="auction_lost"
        ).count()
        == 1
    )


def test_unsold_auction_notifies_seller(app, make_user, make_auction):
    seller = make_user("seller")
    auction = make_auction(seller, start_price=100)

    auction_service.close_auction(auction.id)
    db.session.commit()

    notice = Notification.query.filter_by(
        user_id=seller.id, notification_type="auction_unsold"
    ).first()
    assert notice is not None


def test_mark_notification_read_requires_owner(client, make_user, login):
    owner = make_user("owner")
    other = make_user("other")
    notice = Notification(
        user_id=owner.id,
        notification_type="bid_received",
        title="入札",
        message="テスト",
    )
    db.session.add(notice)
    db.session.commit()

    login("other")
    response = client.post(f"/notifications/{notice.id}/read")
    assert response.status_code == 403
    db.session.expire_all()
    assert Notification.query.get(notice.id).is_read is False

    client.post("/auth/logout")
    login("owner")
    client.post(f"/notifications/{notice.id}/read", follow_redirects=True)
    db.session.expire_all()
    assert Notification.query.get(notice.id).is_read is True


def test_bonus_page_shows_conditions_and_history(client, make_user, login):
    make_user("alice", points=1500)
    login("alice")
    response = client.get("/points/bonus")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "ユーザー登録成功" in body
    assert "初出品成功" in body
    assert "描画の正式保存成功" in body


def test_charge_page_states_payment_is_unavailable(client, make_user, login):
    make_user("alice")
    login("alice")
    response = client.get("/points/charge")
    body = response.get_data(as_text=True)
    assert "課金機能" in body
    assert "Stripe" in body


def test_payment_page_is_reachable(client, make_user, login):
    make_user("alice")
    login("alice")
    response = client.get("/points/payment")
    assert response.status_code == 200
    assert "遷移先のみの画面" in response.get_data(as_text=True)


def test_points_pages_require_login(client):
    assert client.get("/points/bonus").status_code in (302, 401, 403)
    assert client.get("/points/charge").status_code in (302, 401, 403)
