"""入札・返却・終了/落札のテスト（要件定義書 8章「入札」「ポイント」「終了・落札」）。"""
from datetime import timedelta

import pytest

from app.extensions import db
from app.models.auction import Auction
from app.models.artwork import Artwork
from app.models.bid import Bid
from app.models.notification import Notification
from app.models.point import WalletTransaction
from app.models.user import User
from app.services import auction_service
from app.services.auction_service import (
    AuctionError,
    InsufficientPointsError,
    PriceChangedError,
)

from conftest import (
    auction_id_from,
    create_saved_artwork,
    login,
    logout,
    publish,
    register,
)


@pytest.fixture()
def market(app, client):
    """出品者 + 入札者2人 + 開催中のオークション（開始価格100pt）を用意する。"""
    artwork_id = create_saved_artwork(client, "seller")
    auction_id = auction_id_from(publish(client, artwork_id, start_price=100))
    logout(client)
    register(client, "bidder1")
    logout(client)
    register(client, "bidder2")
    logout(client)
    with app.app_context():
        users = {u.username: u.id for u in User.query.all()}
    return {"auction_id": auction_id, "artwork_id": artwork_id, "users": users}


def _user(app, name):
    return User.query.filter_by(username=name).first()


def _bid(app, client, market, name, amount, expected=None):
    logout(client)
    login(client, name)
    data = {"amount": str(amount)}
    if expected is not None:
        data["expected_price"] = str(expected)
    return client.post(
        f"/auctions/{market['auction_id']}/bid", data=data, follow_redirects=True
    )


def test_place_bid_consumes_points_and_updates_price(app, client, market):
    response = _bid(app, client, market, "bidder1", 150)
    assert "150pt で入札しました" in response.get_data(as_text=True)
    with app.app_context():
        auction = Auction.query.get(market["auction_id"])
        assert auction.current_price == 150
        assert _user(app, "bidder1").point_balance == 850
        tx = WalletTransaction.query.filter_by(
            user_id=market["users"]["bidder1"], transaction_type="bid"
        ).first()
        assert tx.amount == -150 and tx.balance_after == 850


def test_seller_cannot_bid(app, client, market):
    logout(client)
    login(client, "seller")
    response = client.post(
        f"/auctions/{market['auction_id']}/bid", data={"amount": "999"},
        follow_redirects=True,
    )
    assert "出品者本人は入札できません" in response.get_data(as_text=True)


def test_bid_must_exceed_current_price(app, client, market):
    response = _bid(app, client, market, "bidder1", 100)
    assert "現在価格" in response.get_data(as_text=True)
    with app.app_context():
        assert Bid.query.count() == 0


def test_insufficient_balance_redirects_to_charge(app, client, market):
    response = _bid(app, client, market, "bidder1", 5000)
    assert response.request.path == "/points/charge"
    with app.app_context():
        assert Bid.query.count() == 0


def test_outbid_refunds_previous_highest_bidder(app, client, market):
    _bid(app, client, market, "bidder1", 300)
    _bid(app, client, market, "bidder2", 400)
    with app.app_context():
        # bidder1: 1000 - 300 + 300(返却) = 1000
        assert _user(app, "bidder1").point_balance == 1000
        # bidder2: 1000 - 400 = 600
        assert _user(app, "bidder2").point_balance == 600
        refund = WalletTransaction.query.filter_by(
            user_id=market["users"]["bidder1"], transaction_type="refund"
        ).first()
        assert refund.amount == 300
        # 高値更新の通知が前最高入札者に届く
        assert Notification.query.filter_by(
            user_id=market["users"]["bidder1"], notification_type="outbid"
        ).count() == 1


def test_highest_bidder_increase_consumes_difference_only(app, client, market):
    _bid(app, client, market, "bidder1", 300)
    _bid(app, client, market, "bidder1", 500)
    with app.app_context():
        # 300消費後、増額は差額の200だけ → 1000 - 300 - 200 = 500
        assert _user(app, "bidder1").point_balance == 500
        # 自分自身の更新では返却が発生しない
        assert WalletTransaction.query.filter_by(
            user_id=market["users"]["bidder1"], transaction_type="refund"
        ).count() == 0


def test_price_change_requires_reconfirmation(app, client, market):
    _bid(app, client, market, "bidder2", 200)
    # 確認時の価格(100)が変わった(200)場合は受理せず再確認を求める
    response = _bid(app, client, market, "bidder1", 250, expected=100)
    assert "再確認" in response.get_data(as_text=True)
    with app.app_context():
        assert Auction.query.get(market["auction_id"]).current_price == 200


def test_bid_after_end_time_rejected(app, client, market):
    with app.app_context():
        auction = Auction.query.get(market["auction_id"])
        auction.end_time = auction_service.utcnow() - timedelta(seconds=1)
        db.session.commit()
    response = _bid(app, client, market, "bidder1", 150)
    assert "終了日時" in response.get_data(as_text=True)
    with app.app_context():
        assert Bid.query.count() == 0


def test_close_auction_with_winner(app, client, market):
    _bid(app, client, market, "bidder1", 300)
    _bid(app, client, market, "bidder2", 500)
    with app.app_context():
        auction = Auction.query.get(market["auction_id"])
        auction.end_time = auction_service.utcnow() - timedelta(seconds=1)
        db.session.commit()
        auction_service.close_expired_auctions()

        auction = Auction.query.get(market["auction_id"])
        assert auction.status == "ended"
        assert auction.winner_id == market["users"]["bidder2"]
        assert auction.final_price == 500
        assert auction.winner_bid_id is not None
        # 落札額は入札時に差し引き済み。落札確定で二重に差し引かない
        assert _user(app, "bidder2").point_balance == 500
        # 出品者へ全額加算（1400 = 登録1000+描画100+初出品300 に +500）
        assert _user(app, "seller").point_balance == 1900
        assert Artwork.query.get(market["artwork_id"]).status == "sold"
        purchase = WalletTransaction.query.filter_by(
            user_id=market["users"]["seller"], transaction_type="purchase"
        ).first()
        assert purchase.amount == 500
        # 落札確定の通知: 落札者・出品者の両方
        assert Notification.query.filter_by(
            user_id=market["users"]["bidder2"], notification_type="auction_won"
        ).count() == 1
        assert Notification.query.filter_by(
            user_id=market["users"]["seller"], notification_type="auction_won"
        ).count() == 1


def test_close_auction_is_idempotent(app, client, market):
    _bid(app, client, market, "bidder1", 250)
    with app.app_context():
        auction = Auction.query.get(market["auction_id"])
        auction.end_time = auction_service.utcnow() - timedelta(seconds=1)
        db.session.commit()
        auction_service.close_expired_auctions()
        auction_service.close_expired_auctions()  # 再実行
        seller = _user(app, "seller")
        assert seller.point_balance == 1400 + 250
        assert WalletTransaction.query.filter_by(
            user_id=market["users"]["seller"], transaction_type="purchase"
        ).count() == 1
        assert Notification.query.filter_by(
            user_id=market["users"]["bidder1"], notification_type="auction_won"
        ).count() == 1


def test_close_without_bids(app, client, market):
    with app.app_context():
        auction = Auction.query.get(market["auction_id"])
        auction.end_time = auction_service.utcnow() - timedelta(seconds=1)
        db.session.commit()
        auction_service.close_expired_auctions()
        auction = Auction.query.get(market["auction_id"])
        assert auction.status == "ended"
        assert auction.winner_id is None
        assert _user(app, "seller").point_balance == 1400
        assert Notification.query.filter_by(
            user_id=market["users"]["seller"], notification_type="auction_lost"
        ).count() == 1
    # 終了後は入札できない
    response = _bid(app, client, market, "bidder1", 150)
    assert "入札を受け付けていません" in response.get_data(as_text=True)


def test_multiple_bids_kept_as_history(app, client, market):
    _bid(app, client, market, "bidder1", 150)
    _bid(app, client, market, "bidder2", 200)
    _bid(app, client, market, "bidder1", 250)
    with app.app_context():
        assert Bid.query.filter_by(auction_id=market["auction_id"]).count() == 3


def test_place_bid_service_rejects_when_ended(app, client, market):
    with app.app_context():
        auction = Auction.query.get(market["auction_id"])
        auction.end_time = auction_service.utcnow() - timedelta(seconds=1)
        db.session.commit()
        bidder = _user(app, "bidder1")
        with pytest.raises(AuctionError):
            auction_service.place_bid(market["auction_id"], bidder, 500)
