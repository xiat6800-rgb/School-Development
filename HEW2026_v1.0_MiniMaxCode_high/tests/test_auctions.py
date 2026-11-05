"""入札・自動入札・終了落札のテスト（要件定義書 5.4〜5.6）。"""

from __future__ import annotations

from datetime import timedelta

from app.extensions import db
from app.models.auto_bid import AutoBidSetting
from app.models.bid import Bid
from app.models.notification import Notification
from app.services import auction_service
from app.services.errors import (
    BusinessRuleError,
    InsufficientPointsError,
    PermissionDeniedError,
    ValidationError,
)
from app.utils import utcnow


def test_place_bid_deducts_points_and_records_history(app, make_user, make_auction):
    seller = make_user("seller")
    bidder = make_user("bidder", points=1000)
    auction = make_auction(seller, start_price=100)

    bid = auction_service.place_bid(auction.id, bidder, 200)
    db.session.commit()

    assert bid.bid_amount == 200
    assert auction.current_price == 200
    assert bidder.point_balance == 800
    assert Bid.query.filter_by(auction_id=auction.id).count() == 1


def test_place_bid_rejects_self_bid(app, make_user, make_auction):
    seller = make_user("seller", points=1000)
    auction = make_auction(seller, start_price=100)

    try:
        auction_service.place_bid(auction.id, seller, 200)
    except PermissionDeniedError:
        pass
    else:  # pragma: no cover - 例外が必要な場面
        raise AssertionError("例外が発生しませんでした")


def test_place_bid_rejects_insufficient_balance(app, make_user, make_auction):
    seller = make_user("seller")
    bidder = make_user("bidder", points=50)
    auction = make_auction(seller, start_price=100)

    try:
        auction_service.place_bid(auction.id, bidder, 200)
    except InsufficientPointsError:
        pass
    else:  # pragma: no cover - 例外が必要な場面
        raise AssertionError("例外が発生しませんでした")
    assert bidder.point_balance == 50


def test_place_bid_rejects_lower_amount(app, make_user, make_auction):
    seller = make_user("seller")
    bidder = make_user("bidder", points=1000)
    auction = make_auction(seller, start_price=100)

    try:
        auction_service.place_bid(auction.id, bidder, 100)
    except ValidationError:
        pass
    else:  # pragma: no cover - 例外が必要な場面
        raise AssertionError("例外が発生しませんでした")


def test_place_bid_rejects_after_end_time(app, make_user, make_auction):
    seller = make_user("seller")
    bidder = make_user("bidder", points=1000)
    auction = make_auction(seller, start_price=100)
    auction.end_time = utcnow() - timedelta(seconds=1)
    db.session.commit()

    try:
        auction_service.place_bid(auction.id, bidder, 200)
    except BusinessRuleError:
        pass
    else:  # pragma: no cover - 例外が必要な場面
        raise AssertionError("例外が発生しませんでした")


def test_higher_bid_refunds_previous_bidder(app, make_user, make_auction):
    seller = make_user("seller")
    first = make_user("first", points=1000)
    second = make_user("second", points=1000)
    auction = make_auction(seller, start_price=100)

    auction_service.place_bid(auction.id, first, 200)
    db.session.commit()
    assert first.point_balance == 800

    auction_service.place_bid(auction.id, second, 300)
    db.session.commit()

    assert first.point_balance == 1000  # 200pt が返還される
    assert second.point_balance == 700
    assert auction.current_price == 300


def test_self_increment_only_consumes_difference(app, make_user, make_auction):
    seller = make_user("seller")
    bidder = make_user("bidder", points=1000)
    auction = make_auction(seller, start_price=100)

    auction_service.place_bid(auction.id, bidder, 200)
    db.session.commit()
    auction_service.place_bid(auction.id, bidder, 250)
    db.session.commit()

    assert bidder.point_balance == 750  # 差額 50 だけ消費


def test_close_auction_records_winner_and_credits_seller(app, make_user, make_auction):
    seller = make_user("seller", points=0)
    bidder = make_user("bidder", points=1000)
    auction = make_auction(seller, start_price=100)

    auction_service.place_bid(auction.id, bidder, 300)
    db.session.commit()

    auction_service.close_auction(auction.id)
    db.session.commit()

    db.session.expire_all()
    closed = type(auction).query.get(auction.id)
    assert closed.status == "ended"
    assert closed.winner_id == bidder.id
    assert closed.final_price == 300
    assert seller.point_balance == 300
    assert closed.artwork.status == "sold"


def test_close_auction_is_idempotent(app, make_user, make_auction):
    seller = make_user("seller", points=0)
    bidder = make_user("bidder", points=1000)
    auction = make_auction(seller, start_price=100)

    auction_service.place_bid(auction.id, bidder, 300)
    db.session.commit()

    auction_service.close_auction(auction.id)
    db.session.commit()
    auction_service.close_auction(auction.id)
    db.session.commit()

    db.session.expire_all()
    assert seller.point_balance == 300  # 二重加算されない
    winner_notifications = Notification.query.filter_by(
        user_id=bidder.id, notification_type="auction_won"
    ).count()
    assert winner_notifications == 1


def test_close_auction_without_bid_has_no_winner(app, make_user, make_auction):
    seller = make_user("seller", points=0)
    auction = make_auction(seller, start_price=100)

    auction_service.close_auction(auction.id)
    db.session.commit()

    db.session.expire_all()
    closed = type(auction).query.get(auction.id)
    assert closed.status == "ended"
    assert closed.winner_id is None
    assert closed.final_price is None
    assert seller.point_balance == 0
    assert closed.artwork.status == "listed"


def test_close_expired_auctions_only_closes_expired(app, make_user, make_auction):
    seller = make_user("seller")
    expired = make_auction(seller, start_price=100)
    running = make_auction(seller, start_price=100)

    expired.end_time = utcnow() - timedelta(minutes=1)
    db.session.commit()

    closed = auction_service.close_expired_auctions()
    db.session.commit()

    assert [auction.id for auction in closed] == [expired.id]
    db.session.expire_all()
    assert type(running).query.get(running.id).status == "active"


def test_auto_bid_raises_after_other_bid(app, make_user, make_auction):
    seller = make_user("seller")
    auto_user = make_user("auto", points=2000)
    manual = make_user("manual", points=2000)
    auction = make_auction(seller, start_price=100)

    auction_service.configure_auto_bid(auto_user, auction, 500)
    db.session.commit()

    auction_service.place_bid(auction.id, manual, 200)
    auction_service.process_auto_bids(auction)
    db.session.commit()

    assert auction.current_price == 201
    assert auto_user.point_balance == 2000 - 201
    auto_bid = Bid.query.filter_by(
        auction_id=auction.id, bidder_id=auto_user.id, is_auto_bid=True
    ).first()
    assert auto_bid is not None
    assert auto_bid.bid_amount == 201


def test_auto_bid_respects_other_bidders_limit(app, make_user, make_auction):
    seller = make_user("seller")
    auto_user = make_user("auto", points=2000)
    manual = make_user("manual", points=2000)
    auction = make_auction(seller, start_price=100)

    auction_service.configure_auto_bid(auto_user, auction, 300)
    db.session.commit()

    auction_service.place_bid(auction.id, manual, 200)
    auction_service.process_auto_bids(auction)
    db.session.commit()

    # 2 番目の自動入札者が居ないため、必要な 201pt だけを競り上げる
    assert auction.current_price == 201


def test_auto_bid_with_equal_limit_prefers_earlier_setting(app, make_user, make_auction):
    seller = make_user("seller")
    early = make_user("early", points=2000)
    late = make_user("late", points=2000)
    manual = make_user("manual", points=2000)
    auction = make_auction(seller, start_price=100)

    auction_service.configure_auto_bid(early, auction, 500)
    auction_service.configure_auto_bid(late, auction, 500)
    db.session.commit()

    auction_service.place_bid(auction.id, manual, 200)
    auction_service.process_auto_bids(auction)
    db.session.commit()

    early_bid = Bid.query.filter_by(
        auction_id=auction.id, bidder_id=early.id, is_auto_bid=True
    ).first()
    late_bid = Bid.query.filter_by(
        auction_id=auction.id, bidder_id=late.id, is_auto_bid=True
    ).first()
    assert early_bid is not None
    assert late_bid is None


def test_auto_bid_stops_when_balance_is_insufficient(app, make_user, make_auction):
    seller = make_user("seller")
    auto_user = make_user("auto", points=10)
    manual = make_user("manual", points=2000)
    auction = make_auction(seller, start_price=100)

    setting = AutoBidSetting(
        auction_id=auction.id, user_id=auto_user.id, max_amount=500, is_active=True
    )
    db.session.add(setting)
    db.session.commit()

    auction_service.place_bid(auction.id, manual, 200)
    auction_service.process_auto_bids(auction)
    db.session.commit()

    db.session.expire_all()
    refreshed = AutoBidSetting.query.get(setting.id)
    assert refreshed.is_active is False
    notice = Notification.query.filter_by(
        user_id=auto_user.id, notification_type="auto_bid_stopped"
    ).first()
    assert notice is not None


def test_configure_auto_bid_rejects_own_auction(app, make_user, make_auction):
    seller = make_user("seller", points=1000)
    auction = make_auction(seller, start_price=100)

    try:
        auction_service.configure_auto_bid(seller, auction, 500)
    except PermissionDeniedError:
        pass
    else:  # pragma: no cover - 例外が必要な場面
        raise AssertionError("例外が発生しませんでした")


def test_configure_auto_bid_requires_affordable_next_bid(app, make_user, make_auction):
    seller = make_user("seller")
    bidder = make_user("bidder", points=50)
    auction = make_auction(seller, start_price=100)

    try:
        auction_service.configure_auto_bid(bidder, auction, 500)
    except InsufficientPointsError:
        pass
    else:  # pragma: no cover - 例外が必要な場面
        raise AssertionError("例外が発生しませんでした")


def test_close_auctions_cli_persists_result(app, runner, make_user, make_auction):
    seller = make_user("seller", points=0)
    bidder = make_user("bidder", points=1000)
    auction = make_auction(seller, start_price=100)

    auction_service.place_bid(auction.id, bidder, 300)
    db.session.commit()
    auction.end_time = utcnow() - timedelta(minutes=1)
    db.session.commit()

    result = runner.invoke(args=["close-auctions"])
    assert result.exit_code == 0

    db.session.expire_all()
    closed = type(auction).query.get(auction.id)
    assert closed.status == "ended"
    assert closed.winner_id == bidder.id
    assert seller.point_balance == 300


def test_bid_via_http_requires_confirmation_then_executes(
    client, make_user, make_auction, login
):
    seller = make_user("seller")
    bidder = make_user("bidder", points=1000)
    auction = make_auction(seller, start_price=100)
    login("bidder")

    response = client.post(
        f"/auctions/{auction.id}/bid",
        data={"bid_amount": "200", "confirmed": "0"},
        follow_redirects=True,
    )
    assert "確定しますか" in response.get_data(as_text=True)
    assert auction.current_price == 100  # 確認段階では変更されない

    response = client.post(
        f"/auctions/{auction.id}/bid",
        data={"bid_amount": "200", "confirmed": "1", "expected_price": "100"},
        follow_redirects=True,
    )
    assert "入札を受け付けました" in response.get_data(as_text=True)
    db.session.expire_all()
    assert type(auction).query.get(auction.id).current_price == 200


def test_bid_with_stale_price_asks_reconfirmation(client, make_user, make_auction, login):
    seller = make_user("seller")
    bidder = make_user("bidder", points=1000)
    auction = make_auction(seller, start_price=100)
    login("bidder")

    response = client.post(
        f"/auctions/{auction.id}/bid",
        data={"bid_amount": "300", "confirmed": "1", "expected_price": "50"},
        follow_redirects=True,
    )
    assert "現在価格が変わりました" in response.get_data(as_text=True)
    db.session.expire_all()
    assert type(auction).query.get(auction.id).current_price == 100
