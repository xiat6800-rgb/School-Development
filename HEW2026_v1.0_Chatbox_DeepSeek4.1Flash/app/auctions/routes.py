"""商品詳細・手動入札・自動入札。"""

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from ..clock import utcnow
from ..extensions import db
from ..models import Artwork
from ..services import auction_service, favorite_service
from ..services.errors import DomainError, PriceChangedError

bp = Blueprint("auctions", __name__, url_prefix="/auctions")


@bp.get("/<int:auction_id>")
def show_auction_detail(auction_id):
    """商品詳細。価格・入札履歴・入札フォーム・自動入札設定を表示する。"""
    auction = auction_service.get_auction(auction_id)
    if auction is None:
        abort(404)

    artwork = auction.artwork
    if artwork is None or not artwork.is_visible_to(current_user):
        abort(404)
    if artwork.auction and artwork.auction.id != auction.id:
        abort(404)

    top_bid = auction_service.get_current_top_bid(auction)
    my_auto_bid = None
    my_favorite = False
    artwork_favorite = False
    if current_user.is_authenticated:
        my_auto_bid = auction_service.get_auto_bid_setting(
            auction.id, current_user.id
        )
        my_favorite = favorite_service.is_auction_favorited(
            current_user.id, auction.id
        )
        artwork_favorite = favorite_service.is_artwork_favorited(
            current_user.id, artwork.id
        )

    return render_template(
        "auctions/detail.html",
        auction=auction,
        artwork=artwork,
        bids=auction_service.list_accepted_bids(auction.id),
        top_bid=top_bid,
        now=utcnow(),
        my_auto_bid=my_auto_bid,
        my_favorite=my_favorite,
        artwork_favorite=artwork_favorite,
        is_seller=auction.is_seller(current_user),
        is_top_bidder=bool(
            top_bid
            and current_user.is_authenticated
            and top_bid.bidder_id == current_user.id
        ),
        can_download=(
            current_user.is_authenticated
            and artwork.is_saved
            and (
                artwork.is_owned_by(current_user)
                or auction.winner_id == current_user.id
            )
        ),
        reconfirm=request.args.get("reconfirm") == "1",
    )


@bp.post("/<int:auction_id>/bids")
@login_required
def submit_bid(auction_id):
    """商品詳細内の入札フォームを受け付ける。"""
    expected = request.form.get("expected_current_price")
    try:
        auction_service.place_bid(
            auction_id,
            current_user.id,
            request.form.get("bid_amount"),
            expected_current_price=expected,
        )
    except PriceChangedError as error:
        flash(str(error), "error")
        return redirect(
            url_for("auctions.show_auction_detail", auction_id=auction_id)
            + "?reconfirm=1"
        )
    except DomainError as error:
        flash(str(error), "error")
    else:
        flash("入札を受け付けました。", "success")
    return redirect(url_for("auctions.show_auction_detail", auction_id=auction_id))


@bp.post("/<int:auction_id>/auto-bid")
@login_required
def set_auto_bid(auction_id):
    """自動入札の上限額を設定・変更する。"""
    try:
        auction_service.configure_auto_bid(
            auction_id, current_user.id, request.form.get("max_amount")
        )
    except DomainError as error:
        flash(str(error), "error")
    else:
        flash("自動入札を設定しました。", "success")
    return redirect(url_for("auctions.show_auction_detail", auction_id=auction_id))


@bp.post("/<int:auction_id>/auto-bid/stop")
@login_required
def stop_auto_bid(auction_id):
    """自動入札を停止する。受理済み入札は取り消さない。"""
    try:
        auction_service.stop_auto_bid(auction_id, current_user.id)
    except DomainError as error:
        flash(str(error), "error")
    else:
        flash("自動入札を停止しました。受理済みの入札は維持されます。", "success")
    return redirect(url_for("auctions.show_auction_detail", auction_id=auction_id))


@bp.get("/artwork/<int:artwork_id>")
def show_artwork_auction(artwork_id):
    """作品から現在の競売へ移動する補助導線。"""
    artwork = db.session.get(Artwork, artwork_id)
    if artwork is None or artwork.auction is None:
        abort(404)
    return redirect(
        url_for("auctions.show_auction_detail", auction_id=artwork.auction.id)
    )
