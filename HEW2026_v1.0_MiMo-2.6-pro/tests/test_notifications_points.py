from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models import Notification, User
from app.services import auction_service, point_service
from tests.conftest import create_auction, create_saved_draft, create_user


def _setup(app, bidder_balance=5000):
    seller_id = create_user(app, "seller")
    bidder_id = create_user(app, "bidder", balance=bidder_balance)
    artwork_id = create_saved_draft(app, seller_id)
    auction_id = create_auction(app, artwork_id, seller_id, start_price=100)
    return seller_id, bidder_id, auction_id


def test_notifications_on_bid_and_outbid(app):
    seller_id, bidder_id, auction_id = _setup(app)
    other_id = create_user(app, "other", balance=5000)
    with app.app_context():
        bidder = db.session.get(User, bidder_id)
        other = db.session.get(User, other_id)
        auction_service.place_bid(auction_id, bidder, 200)
        auction_service.place_bid(auction_id, other, 300)

        seller_notes = Notification.query.filter_by(
            user_id=seller_id, notification_type=Notification.TYPE_BID_RECEIVED
        ).all()
        assert len(seller_notes) == 2

        outbid_notes = Notification.query.filter_by(
            user_id=bidder_id, notification_type=Notification.TYPE_OUTBID
        ).all()
        assert len(outbid_notes) == 1


def test_notifications_on_settlement(app):
    from app.models import Auction

    seller_id, bidder_id, auction_id = _setup(app)
    with app.app_context():
        bidder = db.session.get(User, bidder_id)
        auction_service.place_bid(auction_id, bidder, 250)
        auction = db.session.get(Auction, auction_id)
        auction.end_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
        db.session.commit()
        auction_service.close_auction(auction)
        db.session.commit()

        won = Notification.query.filter_by(
            user_id=bidder_id, notification_type=Notification.TYPE_AUCTION_WON
        ).count()
        sold = Notification.query.filter_by(
            user_id=seller_id, notification_type=Notification.TYPE_AUCTION_SOLD
        ).count()
        assert won == 1
        assert sold == 1


def test_notification_unsold(app):
    seller_id, _, auction_id = _setup(app)
    with app.app_context():
        from app.models import Auction

        auction = db.session.get(Auction, auction_id)
        auction.end_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
        db.session.commit()
        auction_service.close_auction(auction)
        db.session.commit()
        unsold = Notification.query.filter_by(
            user_id=seller_id, notification_type=Notification.TYPE_AUCTION_UNSOLD
        ).count()
        assert unsold == 1


def test_mark_notification_read(app, client):
    from tests.conftest import login

    seller_id, bidder_id, auction_id = _setup(app)
    with app.app_context():
        bidder = db.session.get(User, bidder_id)
        auction_service.place_bid(auction_id, bidder, 200)

    login(client, "seller")
    response = client.get("/notifications")
    assert "入札受付" in response.get_data(as_text=True)

    with app.app_context():
        note = Notification.query.filter_by(user_id=seller_id).first()
        note_id = note.id
    response = client.post(
        f"/notifications/{note_id}/read", follow_redirects=True
    )
    assert response.status_code == 200
    with app.app_context():
        from app.extensions import db as _db

        note = _db.session.get(Notification, note_id)
        assert note.is_read is True


def test_register_bonus_once(app):
    user_id = create_user(app, "alice", balance=0)
    with app.app_context():
        user = db.session.get(User, user_id)
        assert point_service.grant_register_bonus(user) is True
        assert point_service.grant_register_bonus(user) is False
        assert user.point_balance == 1000


def test_drawing_bonus_daily(app):
    user_id = create_user(app, "alice", balance=0)
    with app.app_context():
        user = db.session.get(User, user_id)
        key = point_service.drawing_save_period_key()
        assert point_service.grant_bonus_points(
            user, "drawing_save", 100, period_key=key
        ) is True
        assert point_service.grant_bonus_points(
            user, "drawing_save", 100, period_key=key
        ) is False
        assert user.point_balance == 100


def test_drawing_save_period_key_is_fixed_jst_offset():
    """JST は UTC+9 固定。tz データベースなしで正しい暦日になる。"""
    expected = (
        datetime.now(timezone.utc) + timedelta(hours=9)
    ).strftime("%Y-%m-%d")
    key = point_service.drawing_save_period_key()
    assert key == expected


def test_drawing_save_bonus_without_tz_database(app, monkeypatch):
    """ZoneInfo(\"Asia/Tokyo\") が使えない環境でも保存・ボーナスが動く。"""
    import zoneinfo

    def _raise(*args, **kwargs):
        raise zoneinfo.ZoneInfoNotFoundError("No time zone found with key Asia/Tokyo")

    monkeypatch.setattr(zoneinfo, "ZoneInfo", _raise)

    user_id = create_user(app, "alice", balance=0)
    with app.app_context():
        user = db.session.get(User, user_id)
        assert point_service.drawing_save_period_key() == (
            datetime.now(timezone.utc) + timedelta(hours=9)
        ).strftime("%Y-%m-%d")
        assert point_service.grant_drawing_save_bonus(user) is True
        assert user.point_balance == 100


def test_first_listing_bonus(app):
    seller_id = create_user(app, "seller", balance=0)
    artwork_id = create_saved_draft(app, seller_id)  # 描画保存ボーナス100
    with app.app_context():
        seller = db.session.get(User, seller_id)
        assert seller.point_balance == 100
    create_auction(app, artwork_id, seller_id)  # 初出品300
    with app.app_context():
        seller = db.session.get(User, seller_id)
        assert seller.point_balance == 400
        # 2回目の出品で初出品ボーナスは出ない。
        # 描画保存ボーナスも同日では1回まで。
        artwork2 = create_saved_draft(app, seller_id, title="B")
    create_auction(app, artwork2, seller_id)
    with app.app_context():
        seller = db.session.get(User, seller_id)
        assert seller.point_balance == 400


def test_wallet_balance_consistency(app):
    seller_id, bidder_id, auction_id = _setup(app, bidder_balance=500)
    other_id = create_user(app, "other", balance=500)
    with app.app_context():
        bidder = db.session.get(User, bidder_id)
        other = db.session.get(User, other_id)
        # 初期残高は直接設定されているため、既存取引を差し引いて基準にする
        base = {}
        for uid in (bidder_id, other_id, seller_id):
            u = db.session.get(User, uid)
            existing = sum(t.amount for t in u.wallet_transactions)
            base[uid] = u.point_balance - existing
        auction_service.place_bid(auction_id, bidder, 200)
        auction_service.place_bid(auction_id, other, 300)
        auction_service.place_bid(auction_id, bidder, 400)

        from app.models import WalletTransaction

        for user_id in (bidder_id, other_id, seller_id):
            user = db.session.get(User, user_id)
            txns = (
                WalletTransaction.query.filter_by(user_id=user_id)
                .order_by(WalletTransaction.id)
                .all()
            )
            running = base[user_id]
            for txn in txns:
                running += txn.amount
                assert txn.balance_after == running
            assert user.point_balance == running
            assert user.point_balance >= 0
