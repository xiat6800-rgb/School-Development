from app.extensions import db
from app.models import Artwork, Auction, AutoBid, Bid, User
from app.services.common import BusinessError
from app.services.notification_service import create_notification
from app.utils import utcnow


def refund_unreturned_bid_points(auction, *, now=None):
    bids = Bid.query.filter_by(
        auction_id=auction.id, refunded_at=None
    ).order_by(Bid.id).all()
    user_ids = sorted({bid.bidder_id for bid in bids})
    for user_id in user_ids:
        User.query.filter_by(id=user_id).with_for_update().first()
    refunded = 0
    for bid in bids:
        from app.services.auction_service import refund_bid_points
        if refund_bid_points(bid, now=now):
            refunded += bid.held_amount
    return refunded


def disable_auction_auto_bids(auction):
    AutoBid.query.filter_by(auction_id=auction.id, is_active=True).update(
        {"is_active": False}, synchronize_session=False
    )


def cancel_auction(auction_id, operator, *, reason="", as_admin=False, now=None):
    now = now or utcnow()
    auction = Auction.query.filter_by(id=auction_id).with_for_update().first()
    if not auction:
        raise BusinessError("オークションが見つかりません。")
    if auction.status == "cancelled":
        return auction, False
    if auction.status != "active" or now >= auction.ends_at:
        raise BusinessError("開催中かつ終了日時前のオークションだけ取消できます。")
    if as_admin:
        if not operator.is_admin or not reason.strip():
            raise BusinessError("管理者による取消には理由が必要です。")
    else:
        if auction.artwork.artist_id != operator.id:
            raise BusinessError("自分の出品だけを取消できます。")
        if auction.bids.count():
            raise BusinessError("受理済み入札があるため、出品者本人は取消できません。")

    disable_auction_auto_bids(auction)
    if as_admin:
        refund_unreturned_bid_points(auction, now=now)
    auction.status = "cancelled"
    auction.cancelled_by_id = operator.id
    auction.cancelled_at = now
    auction.cancellation_reason = reason.strip() or "出品者本人による取消"
    auction.artwork.status = "cancelled"
    db.session.flush()

    recipients = {auction.artwork.artist_id: auction.seller}
    for bid in auction.bids:
        recipients[bid.bidder_id] = bid.bidder
    for user_id, user in recipients.items():
        create_notification(
            user, "auction_cancelled", "出品が取り消されました",
            f"『{auction.artwork.title}』のオークションは取り消されました。{auction.cancellation_reason}",
            f"notice:cancelled:{auction.id}:{user_id}", auction=auction,
        )
    return auction, True


def hide_artwork(artwork_id, operator, reason, *, now=None):
    if not operator.is_admin or not reason.strip():
        raise BusinessError("非公開化には管理者権限と理由が必要です。")
    artwork = db.session.get(Artwork, artwork_id)
    if not artwork:
        raise BusinessError("作品が見つかりません。")
    active = artwork.active_auction
    if active:
        cancel_auction(active.id, operator, reason=reason, as_admin=True, now=now)
    artwork.is_public = False
    artwork.visibility_reason = reason.strip()
    artwork.visibility_updated_at = now or utcnow()
    return artwork


def restore_artwork_visibility(artwork_id, operator, reason, *, now=None):
    if not operator.is_admin or not reason.strip():
        raise BusinessError("公開復帰には管理者権限と理由が必要です。")
    artwork = db.session.get(Artwork, artwork_id)
    if not artwork:
        raise BusinessError("作品が見つかりません。")
    artwork.is_public = True
    artwork.visibility_reason = reason.strip()
    artwork.visibility_updated_at = now or utcnow()
    # 取消済みの旧競売は再開しない。
    return artwork
