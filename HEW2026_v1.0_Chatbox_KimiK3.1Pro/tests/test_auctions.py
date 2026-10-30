from datetime import timedelta

import pytest

from app.extensions import db
from app.models import AutoBid, Bid, Notification, WalletTransaction
from app.services.auction_service import (
    close_auction, configure_auto_bid, create_auction, create_relisted_auction,
    place_bid,
)
from app.services.cancellation_service import cancel_auction
from app.services.common import BusinessError
from app.utils import utcnow
from tests.conftest import create_saved_artwork, create_user


def test_bid_refund_and_self_increase_use_only_difference(app):
    with app.app_context():
        seller = create_user("seller")
        bidder1 = create_user("bidder1", 1000)
        bidder2 = create_user("bidder2", 1000)
        artwork = create_saved_artwork(seller)
        auction = create_auction(artwork, 10, 10)
        place_bid(auction.id, bidder1.id, 100)
        assert bidder1.point_balance == 900
        place_bid(auction.id, bidder2.id, 200)
        assert bidder1.point_balance == 1000
        assert bidder2.point_balance == 800
        assert auction.current_price == 200
        place_bid(auction.id, bidder2.id, 250)
        assert bidder2.point_balance == 750
        assert auction.current_bid.held_amount == 50
        assert db.session.get(Bid, auction.current_bid.id).amount == 250
        assert sum(t.amount for t in bidder2.wallet_transactions) == -250


def test_bid_validation_and_stale_confirmation(app):
    with app.app_context():
        seller = create_user("seller")
        bidder = create_user("bidder", 100)
        poor = create_user("poor", 10)
        artwork = create_saved_artwork(seller)
        auction = create_auction(artwork, 20, 5)
        with pytest.raises(BusinessError):
            place_bid(auction.id, seller.id, 100)
        with pytest.raises(BusinessError):
            place_bid(auction.id, bidder.id, 20)
        with pytest.raises(BusinessError):
            place_bid(auction.id, poor.id, 100)
        with pytest.raises(BusinessError):
            place_bid(auction.id, bidder.id, 100, expected_price=999)
        with pytest.raises(BusinessError):
            place_bid(auction.id, bidder.id, 100, now=auction.ends_at)
        assert auction.current_price == 20


def test_autobid_uses_opponent_limit_and_earliest_setting_wins_ties(app):
    with app.app_context():
        seller = create_user("seller")
        first = create_user("first", 1000)
        second = create_user("second", 1000)
        artwork = create_saved_artwork(seller)
        auction = create_auction(artwork, 0, 10)
        early = configure_auto_bid(auction.id, first.id, 100)
        later = AutoBid(auction=auction, user=second, max_amount=100, is_active=True,
                        created_at=early.created_at + timedelta(seconds=1))
        db.session.add(later)
        db.session.flush()
        # 早い設定が先頭のまま維持される。同額の後発設定には負けない。
        assert auction.current_bid.bidder_id == first.id
        assert auction.current_price == 1
        assert first.point_balance == 999
        assert second.point_balance == 1000


def test_autobid_stops_when_execution_balance_is_insufficient(app):
    with app.app_context():
        seller = create_user("seller")
        auto = create_user("auto", 1000)
        other = create_user("other", 1000)
        artwork = create_saved_artwork(seller)
        auction = create_auction(artwork, 0, 10)
        configure_auto_bid(auction.id, auto.id, 100)
        held = auction.current_bid.held_amount
        auto.point_balance = 0
        place_bid(auction.id, other.id, 50)
        assert auto.point_balance == held  # 直前の1ptだけが返還され、次の51ptには不足
        assert not AutoBid.query.filter_by(user_id=auto.id).first().is_active
        assert Notification.query.filter_by(
            user_id=auto.id, notification_type="auto_bid_stopped"
        ).count() == 1


def test_close_is_idempotent_and_pays_seller_without_double_debit(app):
    with app.app_context():
        seller = create_user("seller", 0)
        bidder = create_user("bidder", 500)
        artwork = create_saved_artwork(seller)
        auction = create_auction(artwork, 1, 5)
        place_bid(auction.id, bidder.id, 120)
        seller.point_balance = 0  # 初出品ボーナスと落札代金を分けて検証
        now = auction.ends_at
        close_auction(auction.id, now=now)
        close_auction(auction.id, now=now)
        assert seller.point_balance == 120
        assert bidder.point_balance == 380
        assert auction.winner_id == bidder.id
        assert auction.final_price == 120
        assert WalletTransaction.query.filter_by(
            dedupe_key=f"auction:{auction.id}:sale"
        ).count() == 1


def test_cancel_refund_idempotency_and_relist_preserves_history(app):
    with app.app_context():
        seller = create_user("seller", 0)
        bidder = create_user("bidder", 500)
        admin = create_user("admin", 0, role="admin")
        artwork = create_saved_artwork(seller)
        auction = create_auction(artwork, 1, 5)
        place_bid(auction.id, bidder.id, 150)
        with pytest.raises(BusinessError):
            cancel_auction(auction.id, seller)
        cancel_auction(auction.id, admin, reason="テスト取消", as_admin=True)
        cancel_auction(auction.id, admin, reason="再送", as_admin=True)
        assert bidder.point_balance == 500
        assert artwork.status == "cancelled"
        fresh = create_relisted_auction(artwork, 30, 10)
        assert fresh.id != auction.id
        assert len(artwork.auctions) == 2
        assert artwork.status == "listed"


def test_unsold_close_allows_relist_but_sold_does_not(app):
    with app.app_context():
        seller = create_user("seller")
        artwork = create_saved_artwork(seller)
        auction = create_auction(artwork, 0, 5)
        close_auction(auction.id, now=auction.ends_at)
        assert auction.winner_id is None
        fresh = create_relisted_auction(artwork, 0, 5)
        close_auction(fresh.id, now=fresh.ends_at)
        with pytest.raises(BusinessError):
            create_auction(artwork, 0, 5)
