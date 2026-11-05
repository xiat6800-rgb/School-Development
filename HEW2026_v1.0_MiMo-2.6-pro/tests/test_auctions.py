from datetime import datetime, timedelta, timezone

import pytest

from app.extensions import db
from app.models import Artwork, Auction, Bid, User, WalletTransaction
from app.services import auction_service
from tests.conftest import create_auction, create_saved_draft, create_user


def _setup(app, seller_balance=0, bidder_balance=5000):
    seller_id = create_user(app, "seller", balance=seller_balance)
    bidder_id = create_user(app, "bidder", balance=bidder_balance)
    artwork_id = create_saved_draft(app, seller_id)
    auction_id = create_auction(app, artwork_id, seller_id, start_price=100)
    return seller_id, bidder_id, artwork_id, auction_id


def test_create_auction_validation(app):
    seller_id = create_user(app, "seller")
    artwork_id = create_saved_draft(app, seller_id)
    with app.app_context():
        artwork = db.session.get(Artwork, artwork_id)
        seller = db.session.get(User, seller_id)
        with pytest.raises(auction_service.AuctionError):
            auction_service.create_auction(
                artwork, seller, title="x", description="",
                tag_ids=[], start_price=-1, duration_minutes=10,
            )
        with pytest.raises(auction_service.AuctionError):
            auction_service.create_auction(
                artwork, seller, title="x", description="",
                tag_ids=[], start_price=0, duration_minutes=7,
            )


def test_create_auction_blocked_when_event_cannot_fit(app):
    seller_id = create_user(app, "seller")
    artwork_id = create_saved_draft(app, seller_id)
    app.config["EVENT_END_AT"] = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=7)
    with app.app_context():
        artwork = db.session.get(Artwork, artwork_id)
        seller = db.session.get(User, seller_id)
        with pytest.raises(auction_service.AuctionError):
            auction_service.create_auction(
                artwork, seller, title="x", description="",
                tag_ids=[], start_price=0, duration_minutes=20,
            )
        # 残り5分未満ならすべて不可
        app.config["EVENT_END_AT"] = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=3)
        with pytest.raises(auction_service.AuctionError):
            auction_service.create_auction(
                artwork, seller, title="x", description="",
                tag_ids=[], start_price=0, duration_minutes=5,
            )


def test_create_auction_starts_immediately(app):
    seller_id, _, artwork_id, auction_id = _setup(app)
    with app.app_context():
        auction = db.session.get(Auction, auction_id)
        artwork = db.session.get(Artwork, artwork_id)
        assert auction.status == Auction.STATUS_ACTIVE
        assert auction.current_price == 100
        assert artwork.status == Artwork.STATUS_LISTED


def test_bid_rejects_self_bid(app):
    seller_id, _, _, auction_id = _setup(app)
    with app.app_context():
        auction = db.session.get(Auction, auction_id)
        seller = db.session.get(User, seller_id)
        with pytest.raises(auction_service.BidRejectedError):
            auction_service.place_bid(auction_id, seller, 200)


def test_bid_rejects_low_amount_and_insufficient_balance(app):
    seller_id, bidder_id, _, auction_id = _setup(app, bidder_balance=50)
    with app.app_context():
        bidder = db.session.get(User, bidder_id)
        with pytest.raises(auction_service.BidRejectedError):
            auction_service.place_bid(auction_id, bidder, 100)  # 現在価格と同額
        with pytest.raises(auction_service.BidRejectedError):
            auction_service.place_bid(auction_id, bidder, 500)  # 残高不足


def test_bid_deducts_and_refunds_on_outbid(app):
    seller_id, bidder_id, _, auction_id = _setup(app, bidder_balance=5000)
    other_id = create_user(app, "other", balance=5000)
    with app.app_context():
        bidder = db.session.get(User, bidder_id)
        other = db.session.get(User, other_id)
        auction_service.place_bid(auction_id, bidder, 200)
        assert bidder.point_balance == 4800

        auction_service.place_bid(auction_id, other, 300)
        assert other.point_balance == 4700
        assert bidder.point_balance == 5000  # 前最高入札者へ全額返還

        types = [
            t.transaction_type
            for t in bidder.wallet_transactions.order_by(WalletTransaction.id)
        ]
        assert types == [WalletTransaction.TYPE_BID, WalletTransaction.TYPE_REFUND]


def test_same_bidder_pays_difference_only(app):
    seller_id, bidder_id, _, auction_id = _setup(app, bidder_balance=5000)
    with app.app_context():
        bidder = db.session.get(User, bidder_id)
        auction_service.place_bid(auction_id, bidder, 200)
        auction_service.place_bid(auction_id, bidder, 260)
        # 200pt と差額60pt だけ消費
        assert bidder.point_balance == 5000 - 200 - 60
        auction = db.session.get(Auction, auction_id)
        assert auction.current_price == 260


def test_bid_rejects_when_price_changed(app):
    seller_id, bidder_id, _, auction_id = _setup(app)
    other_id = create_user(app, "other", balance=5000)
    with app.app_context():
        bidder = db.session.get(User, bidder_id)
        other = db.session.get(User, other_id)
        auction_service.place_bid(auction_id, bidder, 200)
        auction_service.place_bid(auction_id, other, 300)
        with pytest.raises(auction_service.BidRejectedError) as exc:
            auction_service.place_bid(
                auction_id, bidder, 400, confirmed_price=200
            )
        assert "価格が変動" in str(exc.value)


def test_bid_rejected_after_end_time(app):
    seller_id, bidder_id, _, auction_id = _setup(app)
    with app.app_context():
        auction = db.session.get(Auction, auction_id)
        auction.end_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
        db.session.commit()
        bidder = db.session.get(User, bidder_id)
        with pytest.raises(auction_service.AuctionNotOpenError):
            auction_service.place_bid(auction_id, bidder, 200)


def test_auto_bid_raises_minimally(app):
    seller_id, alice_id, _, auction_id = _setup(app)
    bob_id = create_user(app, "bob", balance=5000)
    with app.app_context():
        alice = db.session.get(User, alice_id)
        bob = db.session.get(User, bob_id)
        auction_service.configure_auto_bid(alice, auction_id, 400)
        # 設定直後に最小額（101）で自動入札
        auction = db.session.get(Auction, auction_id)
        assert auction.current_price == 101

        # bob（上限300）が設定 → alice が 301 まで必要な額だけ引き上げ
        auction_service.configure_auto_bid(bob, auction_id, 300)
        auction = db.session.get(Auction, auction_id)
        assert auction.current_price == 301
        top = auction_service.get_current_top_bid(auction)
        assert top.bidder_id == alice_id
        assert top.is_auto_bid is True


def test_auto_bid_equal_cap_prefers_earlier(app):
    seller_id, alice_id, _, auction_id = _setup(app)
    bob_id = create_user(app, "bob", balance=5000)
    with app.app_context():
        alice = db.session.get(User, alice_id)
        bob = db.session.get(User, bob_id)
        auction_service.configure_auto_bid(alice, auction_id, 400)
        auction_service.configure_auto_bid(bob, auction_id, 400)
        auction = db.session.get(Auction, auction_id)
        top = auction_service.get_current_top_bid(auction)
        # 同額上限なら先に設定した alice が勝ち、上限まで引き上げられる
        assert top.bidder_id == alice_id
        assert auction.current_price == 400


def test_auto_bid_stops_on_insufficient_balance(app):
    seller_id, _, _, auction_id = _setup(app)
    poor_id = create_user(app, "poor", balance=150)
    rich_id = create_user(app, "rich", balance=5000)
    with app.app_context():
        poor = db.session.get(User, poor_id)
        rich = db.session.get(User, rich_id)
        # poor(残高150)は設定直後 101 で入札できる
        auction_service.configure_auto_bid(poor, auction_id, 500)
        auction = db.session.get(Auction, auction_id)
        assert auction.current_price == 101

        # rich が手動で200pt入札 → poor の自動入札は 201 が必要だが残高不足
        auction_service.place_bid(auction_id, rich, 200)
        auction = db.session.get(Auction, auction_id)
        top = auction_service.get_current_top_bid(auction)
        assert top.bidder_id == rich_id

        from app.models import Notification

        poor_setting = [
            s for s in auction.auto_bid_settings if s.user_id == poor_id
        ][0]
        stopped = Notification.query.filter_by(
            user_id=poor_id,
            notification_type=Notification.TYPE_AUTO_BID_STOPPED,
        ).all()
        assert poor_setting.is_active is False
        assert len(stopped) == 1


def test_auto_bid_rejects_lowering_cap_when_top(app):
    seller_id, alice_id, _, auction_id = _setup(app)
    with app.app_context():
        alice = db.session.get(User, alice_id)
        auction_service.configure_auto_bid(alice, auction_id, 400)
        auction = db.session.get(Auction, auction_id)
        with pytest.raises(auction_service.AutoBidConfigError):
            auction_service.configure_auto_bid(alice, auction_id, 50)


def test_stop_auto_bid_keeps_accepted_bid(app):
    seller_id, alice_id, _, auction_id = _setup(app)
    with app.app_context():
        alice = db.session.get(User, alice_id)
        auction_service.configure_auto_bid(alice, auction_id, 400)
        auction_service.stop_auto_bid(alice, auction_id)
        auction = db.session.get(Auction, auction_id)
        assert auction.current_price == 101
        setting = [s for s in auction.auto_bid_settings if s.user_id == alice_id][0]
        assert setting.is_active is False


def test_close_auction_with_winner(app):
    seller_id, bidder_id, _, auction_id = _setup(app)
    with app.app_context():
        seller = db.session.get(User, seller_id)
        bidder = db.session.get(User, bidder_id)
        # ボーナス（描画100 + 初出品300）込みの基準残高
        base = seller.point_balance
        auction_service.place_bid(auction_id, bidder, 250)
        auction = db.session.get(Auction, auction_id)
        auction.end_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
        db.session.commit()

        auction_service.close_auction(auction)
        db.session.commit()
        auction = db.session.get(Auction, auction_id)
        assert auction.status == Auction.STATUS_ENDED
        assert auction.winner_id == bidder_id
        assert auction.final_price == 250
        assert seller.point_balance == base + 250  # 手数料なしで全額加算
        assert bidder.point_balance == 5000 - 250  # 二重回収なし
        artwork = auction.artwork
        assert artwork.status == Artwork.STATUS_SOLD


def test_close_auction_without_bids(app):
    seller_id, _, _, auction_id = _setup(app)
    with app.app_context():
        seller = db.session.get(User, seller_id)
        base = seller.point_balance
        auction = db.session.get(Auction, auction_id)
        auction.end_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
        db.session.commit()
        auction_service.close_auction(auction)
        db.session.commit()
        auction = db.session.get(Auction, auction_id)
        assert auction.status == Auction.STATUS_ENDED
        assert auction.winner_id is None
        seller = db.session.get(User, seller_id)
        assert seller.point_balance == base  # 変動なし


def test_close_auction_is_idempotent(app):
    seller_id, bidder_id, _, auction_id = _setup(app)
    with app.app_context():
        seller = db.session.get(User, seller_id)
        bidder = db.session.get(User, bidder_id)
        base = seller.point_balance
        auction_service.place_bid(auction_id, bidder, 250)
        auction = db.session.get(Auction, auction_id)
        auction.end_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
        db.session.commit()
        auction_service.close_auction(auction)
        auction_service.close_auction(auction)  # 再実行
        db.session.commit()
        assert seller.point_balance == base + 250
        sales = [
            t for t in seller.wallet_transactions
            if t.transaction_type == WalletTransaction.TYPE_SALE
        ]
        assert len(sales) == 1


def test_close_expired_auctions_command(app):
    from app.commands import close_auctions_command

    seller_id, bidder_id, _, auction_id = _setup(app)
    with app.app_context():
        bidder = db.session.get(User, bidder_id)
        auction_service.place_bid(auction_id, bidder, 150)
        auction = db.session.get(Auction, auction_id)
        auction.end_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
        db.session.commit()

    runner = app.test_cli_runner()
    result = runner.invoke(close_auctions_command)
    assert "closed: 1" in result.output
    with app.app_context():
        auction = db.session.get(Auction, auction_id)
        assert auction.status == Auction.STATUS_ENDED

    result = runner.invoke(close_auctions_command)
    assert "closed: 0" in result.output


def test_download_permissions(app, client):
    from tests.conftest import login

    seller_id, bidder_id, artwork_id, auction_id = _setup(app)
    with app.app_context():
        bidder = db.session.get(User, bidder_id)
        auction_service.place_bid(auction_id, bidder, 250)
        auction = db.session.get(Auction, auction_id)
        auction.end_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
        db.session.commit()
        auction_service.close_auction(auction)
        db.session.commit()

    # 落札者
    login(client, "bidder")
    response = client.get(f"/artworks/{artwork_id}/download/png")
    assert response.status_code == 200
    response = client.get(f"/artworks/{artwork_id}/download/layers")
    assert response.status_code == 200

    # 第三者
    create_user(app, "stranger")
    client.post("/logout")  # 別ユーザーへ切り替える前にログアウト
    login(client, "stranger")
    response = client.get(f"/artworks/{artwork_id}/download/png")
    assert response.status_code == 403
