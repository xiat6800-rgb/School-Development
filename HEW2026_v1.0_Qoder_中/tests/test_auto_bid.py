"""自動入札のテスト（要件定義書 8章「自動入札」）。"""
from datetime import timedelta

import pytest

from app.extensions import db
from app.models.auction import Auction
from app.models.auto_bid import AutoBidSetting
from app.models.notification import Notification
from app.models.user import User
from app.services import auction_service
from app.services.auction_service import AuctionError, InsufficientPointsError

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
    artwork_id = create_saved_artwork(client, "seller")
    auction_id = auction_id_from(publish(client, artwork_id, start_price=100))
    logout(client)
    register(client, "bidder1")
    logout(client)
    register(client, "bidder2")
    logout(client)
    with app.app_context():
        users = {u.username: u.id for u in User.query.all()}
    return {"auction_id": auction_id, "users": users}


def _configure(client, market, name, max_amount):
    logout(client)
    login(client, name)
    return client.post(
        f"/auctions/{market['auction_id']}/auto-bid",
        data={"max_amount": str(max_amount)},
        follow_redirects=True,
    )


def test_set_auto_bid_bids_immediately(app, client, market):
    response = _configure(client, market, "bidder1", 500)
    assert "自動入札" in response.get_data(as_text=True)
    with app.app_context():
        auction = Auction.query.get(market["auction_id"])
        # 設定直後から判定し、勝つために必要な額（現在価格+1pt）だけ入札
        assert auction.current_price == 101
        bidder1 = User.query.filter_by(username="bidder1").first()
        assert bidder1.point_balance == 1000 - 101


def test_auto_bid_requires_balance_for_next_bid(app, client, market):
    with app.app_context():
        bidder2 = User.query.filter_by(username="bidder2").first()
        bidder2.point_balance = 50
        db.session.commit()
    response = _configure(client, market, "bidder2", 500)
    assert "残高が不足" in response.get_data(as_text=True)
    with app.app_context():
        assert AutoBidSetting.query.count() == 0


def test_max_amount_may_exceed_balance_if_next_bid_payable(app, client, market):
    response = _configure(client, market, "bidder1", 5000)
    # 上限自体は残高（1000pt）を超えてよい
    assert "自動入札の上限を 5000pt に設定しました" in response.get_data(as_text=True)
    with app.app_context():
        assert Auction.query.get(market["auction_id"]).current_price == 101


def test_auto_bids_escalate_within_max(app, client, market):
    _configure(client, market, "bidder1", 500)
    _configure(client, market, "bidder2", 200)
    with app.app_context():
        auction = Auction.query.get(market["auction_id"])
        # bidder2 の上限200に対し、bidder1 が必要な額（201pt）だけ競り上げる
        assert auction.current_price == 201
        highest = auction.highest_bid
        assert highest.bidder.username == "bidder1"
        assert highest.is_auto_bid
        # bidder2 は勝てないため実際には消費しない（上限全額は確保しない）
        assert User.query.filter_by(username="bidder2").first().point_balance == 1000
        # bidder1: 101 + 差額100 = 201pt 消費
        assert User.query.filter_by(username="bidder1").first().point_balance == 799


def test_equal_max_prefers_earlier_setting(app, client, market):
    _configure(client, market, "bidder1", 300)
    _configure(client, market, "bidder2", 300)
    with app.app_context():
        auction = Auction.query.get(market["auction_id"])
        # 同額上限は設定日時が早い bidder1 が優先され、上限額で決着する
        assert auction.current_price == 300
        assert auction.highest_bid.bidder.username == "bidder1"
        assert User.query.filter_by(username="bidder2").first().point_balance == 1000


def test_insufficient_balance_at_runtime_stops_and_notifies(app, client, market):
    _configure(client, market, "bidder1", 900)
    with app.app_context():
        bidder1 = User.query.filter_by(username="bidder1").first()
        # 実行時の残高不足を再現: 残高を減らしてから他者に入札させる
        bidder1.point_balance = 0
        db.session.commit()
    logout(client)
    login(client, "bidder2")
    client.post(
        f"/auctions/{market['auction_id']}/bid", data={"amount": "140"},
        follow_redirects=True,
    )
    with app.app_context():
        setting = AutoBidSetting.query.filter_by(
            user_id=market["users"]["bidder1"]
        ).first()
        assert setting.is_active is False
        assert Notification.query.filter_by(
            user_id=market["users"]["bidder1"],
            notification_type="auto_bid_stopped",
        ).count() == 1
        # bidder1 の自動入札は実行されず、bidder2 が最高入札者のまま
        auction = Auction.query.get(market["auction_id"])
        assert auction.current_price == 140
        assert auction.highest_bid.bidder.username == "bidder2"


def test_cannot_lower_max_below_accepted_bid(app, client, market):
    _configure(client, market, "bidder1", 500)
    with app.app_context():
        auction = Auction.query.get(market["auction_id"])
        bidder1 = User.query.filter_by(username="bidder1").first()
        with pytest.raises(AuctionError):
            auction_service.configure_auto_bid(auction.id, bidder1, 50)
        # 停止しても受理済み入札は維持
        auction_service.stop_auto_bid(auction.id, bidder1)
        assert auction.current_price == 101
        assert auction.highest_bid.bidder_id == bidder1.id


def test_seller_cannot_set_auto_bid(app, client, market):
    with app.app_context():
        auction = Auction.query.get(market["auction_id"])
        seller = User.query.filter_by(username="seller").first()
        with pytest.raises(AuctionError):
            auction_service.configure_auto_bid(auction.id, seller, 500)


def test_stop_auto_bid_keeps_accepted_bids(app, client, market):
    _configure(client, market, "bidder1", 500)
    response = _configure_stop(client, market, "bidder1")
    assert "停止しました" in response.get_data(as_text=True)
    # 他者の入札後も自動では競り上がらない
    logout(client)
    login(client, "bidder2")
    client.post(
        f"/auctions/{market['auction_id']}/bid", data={"amount": "200"},
        follow_redirects=True,
    )
    with app.app_context():
        auction = Auction.query.get(market["auction_id"])
        assert auction.current_price == 200
        assert auction.highest_bid.bidder.username == "bidder2"
        assert bid_count(auction) == 2  # bidder1 の受理済み入札は履歴に残る


def _configure_stop(client, market, name):
    logout(client)
    login(client, name)
    return client.post(
        f"/auctions/{market['auction_id']}/auto-bid/stop",
        data={}, follow_redirects=True,
    )


def bid_count(auction):
    from app.models.bid import Bid

    return Bid.query.filter_by(auction_id=auction.id, bid_status="accepted").count()
