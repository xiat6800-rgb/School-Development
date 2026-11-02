"""xhigh 版で追加・変更したモデルの確認。"""

from app.extensions import db
from app.models.artwork import Artwork
from app.models.auction import Auction
from app.models.bid import Bid
from app.models.cancellation import AuctionCancellation
from app.models.notification import Notification
from app.models.wallet import WalletTransaction


def test_auction_has_active_slot_and_previous_link(app):
    columns = {c.name for c in Auction.__table__.columns}
    assert "active_slot" in columns
    assert "previous_auction_id" in columns


def test_artwork_auction_relationship_is_a_list(app):
    relationship = Artwork.__mapper__.relationships["auction"]
    assert isinstance(relationship.uselist, bool)
    assert relationship.uselist is True


def test_bid_tracks_held_points(app):
    assert "held_points" in {c.name for c in Bid.__table__.columns}


def test_wallet_transaction_has_reference_key(app):
    columns = {c.name for c in WalletTransaction.__table__.columns}
    assert "reference_key" in columns


def test_notification_can_be_revoked(app):
    columns = {c.name for c in Notification.__table__.columns}
    assert {"revoked_at", "revoked_by_id", "revoke_reason"} <= columns


def test_auction_cancellations_table_exists(app):
    assert db.session.execute(
        db.text("SHOW TABLES LIKE 'auction_cancellations'")
    ).first() is not None


def test_only_one_active_auction_per_artwork(app, make_user, make_artwork):
    """UNIQUE (artwork_id, active_slot) が開催中 1 件しか作れないこと。"""
    from sqlalchemy.exc import IntegrityError

    seller = make_user("seller")
    artwork = make_artwork(seller)
    now = db.func.now()
    db.session.add(
        Auction(
            artwork_id=artwork.id,
            start_price=1,
            current_price=1,
            status="active",
            active_slot=1,
            start_time=now,
            end_time=now,
        )
    )
    db.session.commit()
    db.session.add(
        Auction(
            artwork_id=artwork.id,
            start_price=1,
            current_price=1,
            status="active",
            active_slot=1,
            start_time=now,
            end_time=now,
        )
    )
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
    else:
        db.session.rollback()
        raise AssertionError("同時開催の競売が 2 件作れてしまった")


def test_closed_auction_frees_the_active_slot(app, make_user, make_artwork):
    """終了後は active_slot が NULL になり、再出品の余地ができる。"""
    seller = make_user("seller")
    artwork = make_artwork(seller)
    now = db.func.now()
    auction = Auction(
        artwork_id=artwork.id,
        start_price=1,
        current_price=1,
        status="active",
        active_slot=1,
        start_time=now,
        end_time=now,
    )
    db.session.add(auction)
    db.session.commit()
    auction.status = "ended"
    auction.active_slot = None
    db.session.commit()
    db.session.add(
        Auction(
            artwork_id=artwork.id,
            start_price=1,
            current_price=1,
            status="active",
            active_slot=1,
            start_time=now,
            end_time=now,
        )
    )
    db.session.commit()
    assert Auction.query.filter_by(artwork_id=artwork.id).count() == 2


def test_auction_cancellation_record_fields(app):
    columns = {c.name for c in AuctionCancellation.__table__.columns}
    assert {
        "auction_id",
        "artwork_id",
        "action",
        "actor_id",
        "reason",
        "refunded_points",
    } <= columns
