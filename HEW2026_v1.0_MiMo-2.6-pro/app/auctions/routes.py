from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.models import Auction, AutoBidSetting, Bid
from app.services import auction_service

bp = Blueprint("auctions", __name__)


def _get_auction_or_404(auction_id):
    from app.extensions import db

    auction = db.session.get(Auction, auction_id)
    if auction is None:
        abort(404)
    return auction


@bp.route("/auctions/<int:auction_id>", methods=["GET"])
def show_auction_detail(auction_id):
    auction = _get_auction_or_404(auction_id)
    artwork = auction.artwork
    bids = (
        Bid.query.filter_by(auction_id=auction.id, bid_status=Bid.STATUS_ACCEPTED)
        .order_by(Bid.bid_amount.desc(), Bid.id.desc())
        .all()
    )
    top_bid = bids[0] if bids else None
    my_setting = None
    if current_user.is_authenticated:
        my_setting = AutoBidSetting.query.filter_by(
            auction_id=auction.id, user_id=current_user.id
        ).first()
    return render_template(
        "auctions/detail.html",
        auction=auction,
        artwork=artwork,
        bids=bids,
        top_bid=top_bid,
        my_setting=my_setting,
    )


@bp.route("/auctions/<int:auction_id>/bid", methods=["POST"])
@login_required
def submit_bid(auction_id):
    auction = _get_auction_or_404(auction_id)
    amount = request.form.get("amount", type=int)
    confirmed_price = request.form.get("confirmed_price", type=int)
    try:
        auction_service.place_bid(
            auction.id, current_user, amount, confirmed_price=confirmed_price
        )
        flash("入札を受け付けました。", "success")
    except auction_service.BidRejectedError as exc:
        flash(str(exc), "error")
        if "価格が変動" in str(exc):
            return redirect(url_for("auctions.show_auction_detail", auction_id=auction.id))
    except auction_service.AuctionError as exc:
        flash(str(exc), "error")
    return redirect(url_for("auctions.show_auction_detail", auction_id=auction.id))


@bp.route("/auctions/<int:auction_id>/auto-bid", methods=["POST"])
@login_required
def set_auto_bid(auction_id):
    auction = _get_auction_or_404(auction_id)
    max_amount = request.form.get("max_amount", type=int)
    try:
        auction_service.configure_auto_bid(current_user, auction.id, max_amount)
        flash("自動入札を設定しました。", "success")
    except auction_service.AutoBidConfigError as exc:
        flash(str(exc), "error")
    return redirect(url_for("auctions.show_auction_detail", auction_id=auction.id))


@bp.route("/auctions/<int:auction_id>/auto-bid/stop", methods=["POST"])
@login_required
def stop_auto_bid(auction_id):
    auction = _get_auction_or_404(auction_id)
    try:
        auction_service.stop_auto_bid(current_user, auction.id)
        flash("自動入札を停止しました。", "success")
    except auction_service.AutoBidConfigError as exc:
        flash(str(exc), "error")
    return redirect(url_for("auctions.show_auction_detail", auction_id=auction.id))
