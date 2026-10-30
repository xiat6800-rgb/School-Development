from flask import (
    abort, flash, jsonify, redirect, render_template, request, url_for,
)
from flask_login import current_user, login_required

from app.auctions import bp
from app.extensions import db
from app.models import ArtworkFavorite, Auction, AuctionFavorite, AutoBid, Bid
from app.services.auction_service import (
    close_auction, configure_auto_bid, place_bid, stop_auto_bid,
)
from app.services.cancellation_service import cancel_auction
from app.services.common import BusinessError
from app.utils import utcnow


def _get_visible_auction(auction_id):
    auction = db.session.get(Auction, auction_id) or abort(404)
    if auction.status == "active" and utcnow() >= auction.ends_at:
        close_auction(auction.id)
        db.session.commit()
    artwork = auction.artwork
    is_winner = current_user.is_authenticated and auction.winner_id == current_user.id
    if not artwork.is_public and not (
        current_user.is_authenticated
        and (current_user.id == artwork.artist_id or is_winner or current_user.is_admin)
    ):
        abort(404)
    return auction


def _context(auction, pending_bid=None):
    artwork_favorite = auction_favorite = auto_bid = None
    if current_user.is_authenticated:
        artwork_favorite = ArtworkFavorite.query.filter_by(
            user_id=current_user.id, artwork_id=auction.artwork_id
        ).first()
        auction_favorite = AuctionFavorite.query.filter_by(
            user_id=current_user.id, auction_id=auction.id
        ).first()
        auto_bid = AutoBid.query.filter_by(
            user_id=current_user.id, auction_id=auction.id
        ).first()
    bids = Bid.query.filter_by(auction_id=auction.id).order_by(Bid.id.desc()).limit(50).all()
    return {
        "auction": auction, "bids": bids, "pending_bid": pending_bid,
        "artwork_favorite": artwork_favorite, "auction_favorite": auction_favorite,
        "auto_bid": auto_bid, "now": utcnow(),
    }


@bp.get("/<int:auction_id>")
def show_auction_detail(auction_id):
    auction = _get_visible_auction(auction_id)
    return render_template("auctions/detail.html", **_context(auction))


@bp.post("/<int:auction_id>/bid")
@login_required
def submit_bid(auction_id):
    auction = _get_visible_auction(auction_id)
    try:
        amount = int(request.form.get("amount", ""))
        expected_price = int(request.form.get("expected_price", ""))
    except ValueError as exc:
        raise BusinessError("入札額は整数ptで入力してください。") from exc
    if request.form.get("phase") == "review":
        if amount <= auction.current_price:
            raise BusinessError(f"入札額は{auction.current_price + 1:,}pt以上にしてください。")
        pending = {"amount": amount, "expected_price": expected_price}
        return render_template("auctions/detail.html", **_context(auction, pending))
    place_bid(auction.id, current_user.id, amount, expected_price=expected_price)
    db.session.commit()
    flash("入札を受理しました。自動入札がある場合は最新価格も確認してください。", "success")
    return redirect(url_for("auctions.show_auction_detail", auction_id=auction.id))


@bp.post("/<int:auction_id>/auto-bid")
@login_required
def set_auto_bid(auction_id):
    try:
        max_amount = int(request.form.get("max_amount", ""))
    except ValueError as exc:
        raise BusinessError("上限額は整数ptで入力してください。") from exc
    configure_auto_bid(auction_id, current_user.id, max_amount)
    db.session.commit()
    flash("自動入札を設定しました。上限全額ではなく、受理額だけを消費します。", "success")
    return redirect(url_for("auctions.show_auction_detail", auction_id=auction_id))


@bp.post("/<int:auction_id>/auto-bid/stop")
@login_required
def stop_auto_bid_route(auction_id):
    stop_auto_bid(auction_id, current_user.id)
    db.session.commit()
    flash("自動入札を停止しました。受理済み入札は維持されます。", "success")
    return redirect(url_for("auctions.show_auction_detail", auction_id=auction_id))


@bp.post("/<int:auction_id>/cancel")
@login_required
def cancel_own_auction(auction_id):
    cancel_auction(auction_id, current_user)
    db.session.commit()
    flash("出品を取り消しました。作品履歴は残り、再出品できます。", "success")
    return redirect(url_for("auctions.show_auction_detail", auction_id=auction_id))


@bp.get("/<int:auction_id>/status")
def auction_status(auction_id):
    auction = _get_visible_auction(auction_id)
    current = auction.current_bid
    return jsonify({
        "status": auction.status,
        "current_price": auction.current_price,
        "current_bidder": current.bidder.display_name if current else None,
        "ends_at": auction.ends_at.isoformat() + "Z",
        "winner": auction.winner.display_name if auction.winner else None,
        "bids": [{
            "id": bid.id, "amount": bid.amount, "auto": bid.is_auto,
            "bidder": bid.bidder.display_name, "created_at": bid.created_at.isoformat() + "Z",
        } for bid in Bid.query.filter_by(auction_id=auction.id).order_by(Bid.id.desc()).limit(20)],
    })
