"""商品詳細画面と画面内入札（要件定義書 5.4〜5.6）。"""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from app.models import ArtworkBookmark, Auction, AutoBidSetting, Bid, Bookmark
from app.services import auction_service
from app.services.auction_service import BidError
from app.utils import utcnow

bp = Blueprint("auctions", __name__, url_prefix="/auctions")


def _accepted_bids(auction):
    bids = (
        db.session.execute(
            select(Bid)
            .where(Bid.auction_id == auction.id, Bid.bid_status == "accepted")
            .order_by(Bid.bid_amount.desc(), Bid.created_at.asc())
        )
        .scalars()
        .all()
    )
    return bids


@bp.route("/<int:auction_id>")
def detail(auction_id):
    auction = db.session.get(Auction, auction_id)
    if auction is None or auction.artwork is None:
        abort(404)
    # 下書きは公開しない
    if auction.artwork.status not in {"listed", "sold"}:
        abort(404)

    bids = _accepted_bids(auction)
    highest = bids[0] if bids else None
    is_seller = (
        current_user.is_authenticated and current_user.id == auction.artwork.seller_id
    )

    artwork_favorite = False
    auction_favorite = False
    my_auto_bid = None
    if current_user.is_authenticated:
        artwork_favorite = (
            db.session.query(ArtworkBookmark)
            .filter(
                ArtworkBookmark.user_id == current_user.id,
                ArtworkBookmark.artwork_id == auction.artwork_id,
            )
            .first()
            is not None
        )
        auction_favorite = (
            db.session.query(Bookmark)
            .filter(
                Bookmark.user_id == current_user.id,
                Bookmark.auction_id == auction.id,
            )
            .first()
            is not None
        )
        my_auto_bid = (
            db.session.query(AutoBidSetting)
            .filter(
                AutoBidSetting.auction_id == auction.id,
                AutoBidSetting.user_id == current_user.id,
                AutoBidSetting.is_active.is_(True),
            )
            .first()
        )

    return render_template(
        "auctions/detail.html",
        auction=auction,
        bids=bids,
        highest=highest,
        is_seller=is_seller,
        artwork_favorite=artwork_favorite,
        auction_favorite=auction_favorite,
        my_auto_bid=my_auto_bid,
        now=utcnow(),
    )


@bp.route("/<int:auction_id>/bid", methods=["POST"])
@login_required
def bid(auction_id):
    raw_amount = (request.form.get("amount") or "").strip()
    if not raw_amount.isdigit():
        flash("入札額は 1pt 以上の整数で入力してください。", "error")
        return redirect(url_for("auctions.detail", auction_id=auction_id))

    try:
        accepted = auction_service.place_bid(
            auction_id, current_user.id, int(raw_amount)
        )
    except BidError as exc:
        db.session.rollback()
        flash(str(exc), "error")
        return redirect(url_for("auctions.detail", auction_id=auction_id))

    flash(
        f"{accepted.bid_amount}pt で入札を受け付けました。現在価格は {accepted.bid_amount}pt です。",
        "success",
    )
    return redirect(url_for("auctions.detail", auction_id=auction_id) + "#bids")


@bp.route("/<int:auction_id>/auto-bid", methods=["POST"])
@login_required
def auto_bid(auction_id):
    raw_amount = (request.form.get("max_amount") or "").strip()
    if not raw_amount.isdigit():
        flash("上限額は 1pt 以上の整数で入力してください。", "error")
        return redirect(url_for("auctions.detail", auction_id=auction_id))

    try:
        auction_service.set_auto_bid(auction_id, current_user.id, int(raw_amount))
    except BidError as exc:
        db.session.rollback()
        flash(str(exc), "error")
        return redirect(url_for("auctions.detail", auction_id=auction_id))

    flash(
        "自動入札を設定しました。他のユーザーの入札に合わせて上限額まで自動で入札します。",
        "success",
    )
    return redirect(url_for("auctions.detail", auction_id=auction_id) + "#auto-bid")
