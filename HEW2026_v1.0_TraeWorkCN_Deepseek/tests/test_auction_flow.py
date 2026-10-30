from datetime import timedelta

import pytest

from app.extensions import db
from app.models import Artwork, Auction, AutoBidSetting, Bid, Notification, User
from app.services import auction_service
from app.services.auction_service import BidError
from app.services.bonus_service import grant_listing_bonus
from app.utils import to_jst, utcnow

from tests.conftest import create_user, login


def create_auction(seller, start_price=100, days=1):
    artwork = Artwork(
        seller_id=seller.id,
        title="テスト作品",
        description="説明",
        image_path="dummy.png",
        status="listed",
    )
    db.session.add(artwork)
    db.session.flush()
    auction = Auction(
        artwork_id=artwork.id,
        start_price=start_price,
        current_price=start_price,
        status="active",
        start_time=utcnow(),
        end_time=utcnow() + timedelta(days=days),
    )
    db.session.add(auction)
    db.session.commit()
    return auction


def test_manual_bid_deducts_and_refunds_previous_highest(app):
    seller = create_user("seller", "seller@example.com")
    bidder1 = create_user("bidder1", "b1@example.com", balance=5000)
    bidder2 = create_user("bidder2", "b2@example.com", balance=5000)
    auction = create_auction(seller)

    auction_service.place_bid(auction.id, bidder1.id, 150)
    db.session.refresh(bidder1)
    assert bidder1.point_balance == 4850

    auction_service.place_bid(auction.id, bidder1.id, 200)
    db.session.refresh(bidder1)
    db.session.refresh(auction)
    assert bidder1.point_balance == 4800
    assert auction.current_price == 200

    auction_service.place_bid(auction.id, bidder2.id, 300)
    db.session.refresh(bidder1)
    db.session.refresh(bidder2)
    db.session.refresh(auction)
    assert bidder1.point_balance == 5000  # 200pt 返却
    assert bidder2.point_balance == 4700
    assert auction.current_price == 300
    assert db.session.query(Bid).filter_by(auction_id=auction.id).count() == 3


def test_auto_bid_follows_up_to_limit(app):
    seller = create_user("seller2", "seller2@example.com")
    bidder1 = create_user("auto1", "auto1@example.com", balance=5000)
    bidder2 = create_user("auto2", "auto2@example.com", balance=5000)
    auction = create_auction(seller)

    auction_service.set_auto_bid(auction.id, bidder2.id, 400)
    auction_service.place_bid(auction.id, bidder1.id, 200)

    db.session.refresh(auction)
    db.session.refresh(bidder1)
    db.session.refresh(bidder2)
    assert auction.current_price == 300
    assert bidder1.point_balance == 5000
    assert bidder2.point_balance == 4700

    highest = auction_service.highest_bid(auction)
    assert highest.bidder_id == bidder2.id
    assert highest.is_auto_bid is True


def test_auto_bid_same_limit_prioritises_earlier_setting(app):
    seller = create_user("seller3", "seller3@example.com")
    bidder1 = create_user("tie1", "tie1@example.com", balance=5000)
    bidder2 = create_user("tie2", "tie2@example.com", balance=5000)
    bidder3 = create_user("tie3", "tie3@example.com", balance=5000)
    auction = create_auction(seller)

    earlier = AutoBidSetting(
        auction_id=auction.id,
        user_id=bidder2.id,
        max_amount=500,
        is_active=True,
        created_at=utcnow() - timedelta(minutes=5),
    )
    db.session.add(earlier)
    db.session.commit()

    auction_service.set_auto_bid(auction.id, bidder3.id, 500)
    auction_service.place_bid(auction.id, bidder1.id, 110)

    db.session.refresh(auction)
    highest = auction_service.highest_bid(auction)
    # 同額上限では設定日時が早いユーザーが最高額を維持する
    assert highest.bidder_id == bidder2.id
    assert auction.current_price == 410


def test_bid_rejections(app):
    seller = create_user("seller4", "seller4@example.com")
    poor = create_user("poor", "poor@example.com", balance=50)
    bidder = create_user("normal", "normal@example.com", balance=5000)
    auction = create_auction(seller)

    with pytest.raises(BidError):
        auction_service.place_bid(auction.id, seller.id, 200)  # 自己入札
    with pytest.raises(BidError):
        auction_service.place_bid(auction.id, bidder.id, 100)  # 現在価格と同額
    with pytest.raises(BidError):
        auction_service.place_bid(auction.id, poor.id, 200)  # 残高不足

    auction.end_time = utcnow() - timedelta(seconds=1)
    db.session.commit()
    with pytest.raises(BidError):
        auction_service.place_bid(auction.id, bidder.id, 200)  # 終了後
    db.session.rollback()


def test_close_auction_records_winner_without_double_deduction(app):
    seller = create_user("seller5", "seller5@example.com")
    bidder = create_user("winner", "winner@example.com", balance=1000)
    auction = create_auction(seller)

    auction_service.place_bid(auction.id, bidder.id, 250)
    db.session.refresh(bidder)
    balance_after_bid = bidder.point_balance

    auction.end_time = utcnow() - timedelta(seconds=1)
    db.session.commit()
    closed = auction_service.close_auctions()

    db.session.refresh(auction)
    db.session.refresh(bidder)
    assert auction.id in closed
    assert auction.status == "ended"
    assert auction.winner_id == bidder.id
    assert auction.final_price == 250
    assert auction.artwork.status == "sold"
    assert bidder.point_balance == balance_after_bid  # 再差し引きしない

    notification = (
        db.session.query(Notification)
        .filter_by(user_id=bidder.id, notification_type="auction_won")
        .first()
    )
    assert notification is not None


def test_close_auction_without_bids_keeps_artwork_listed(app):
    seller = create_user("seller6", "seller6@example.com")
    auction = create_auction(seller)
    auction.end_time = utcnow() - timedelta(seconds=1)
    db.session.commit()

    auction_service.close_auctions()
    db.session.refresh(auction)
    assert auction.status == "ended"
    assert auction.winner_id is None
    assert auction.artwork.status == "listed"


def test_listing_from_draft_creates_auction_and_first_listing_bonus(client, app):
    seller = create_user("lister", "lister@example.com")
    artwork = Artwork(
        seller_id=seller.id, title="無題", image_path="dummy.png", status="draft"
    )
    db.session.add(artwork)
    db.session.commit()

    login(client, "lister@example.com")
    end_time = (to_jst(utcnow() + timedelta(days=2))).strftime("%Y-%m-%dT%H:%M")
    response = client.post(
        f"/artworks/{artwork.id}/listing",
        data={
            "title": "出品テスト",
            "description": "説明文",
            "tags": ["1", "2"],
            "start_price": "300",
            "end_time": end_time,
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    db.session.refresh(artwork)
    assert artwork.status == "listed"
    assert artwork.title == "出品テスト"
    auction = db.session.query(Auction).filter_by(artwork_id=artwork.id).one()
    assert auction.status == "active"
    assert auction.current_price == 300
    assert {tag.id for tag in artwork.tags} == {1, 2}

    db.session.refresh(seller)
    assert seller.point_balance == app.config["BONUS_FIRST_LISTING_POINTS"]


def test_bid_through_detail_page(client, app):
    seller = create_user("s7", "s7@example.com")
    bidder = create_user("buyer", "buyer@example.com", balance=2000)
    auction = create_auction(seller, start_price=100)

    login(client, "buyer@example.com")
    response = client.post(
        f"/auctions/{auction.id}/bid", data={"amount": "150"}, follow_redirects=True
    )
    assert response.status_code == 200
    assert "入札を受け付けました" in response.get_data(as_text=True)

    db.session.refresh(auction)
    db.session.refresh(bidder)
    assert auction.current_price == 150
    assert bidder.point_balance == 1850


def test_bid_form_rejects_non_integer(client, app):
    seller = create_user("s8", "s8@example.com")
    create_user("buyer8", "buyer8@example.com", balance=2000)
    auction = create_auction(seller)

    login(client, "buyer8@example.com")
    response = client.post(
        f"/auctions/{auction.id}/bid", data={"amount": "abc"}, follow_redirects=True
    )
    assert "整数" in response.get_data(as_text=True)
