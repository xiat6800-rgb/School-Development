"""商品詳細・入札・自動入札のルート。"""
from flask import (
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from ..extensions import db
from ..models.auction import Auction
from ..models.auto_bid import AutoBidSetting
from ..models.bid import Bid
from ..models.favorite import AuctionFavorite
from ..services import auction_service
from ..services.auction_service import (
    AuctionError,
    InsufficientPointsError,
    PriceChangedError,
)
from . import bp


def _get_auction(auction_id):
    auction = db.session.get(Auction, auction_id)
    if auction is None:
        abort(404)
    return auction


@bp.route("/auctions/<int:auction_id>")
def show_auction_detail(auction_id):
    """オークションIDで作品・価格・履歴・入札結果を表示する。"""
    auction = _get_auction(auction_id)
    bids = (
        Bid.query.filter_by(auction_id=auction.id, bid_status="accepted")
        .order_by(Bid.created_at.desc(), Bid.id.desc())
        .all()
    )
    my_setting = None
    is_favorite = False
    if current_user.is_authenticated:
        my_setting = AutoBidSetting.query.filter_by(
            auction_id=auction.id, user_id=current_user.id
        ).first()
        is_favorite = (
            AuctionFavorite.query.filter_by(
                auction_id=auction.id, user_id=current_user.id
            ).first()
            is not None
        )
    return render_template(
        "auctions/detail.html",
        auction=auction,
        bids=bids,
        my_setting=my_setting,
        is_favorite=is_favorite,
        min_bid=auction.current_price + 1,
    )


@bp.route("/auctions/<int:auction_id>/state")
def show_auction_state(auction_id):
    """価格・入札履歴を3秒以内の間隔で更新するための JSON エンドポイント。"""
    auction = _get_auction(auction_id)
    bids = (
        Bid.query.filter_by(auction_id=auction.id, bid_status="accepted")
        .order_by(Bid.created_at.desc(), Bid.id.desc())
        .limit(10)
        .all()
    )
    return jsonify(
        status=auction.status,
        current_price=auction.current_price,
        end_time=auction.end_time.isoformat() + "Z",
        winner_id=auction.winner_id,
        final_price=auction.final_price,
        bids=[
            {
                "amount": bid.bid_amount,
                "bidder": bid.bidder.disp_name,
                "is_auto": bid.is_auto_bid,
                "created_at": bid.created_at.isoformat() + "Z",
            }
            for bid in bids
        ],
    )


@bp.route("/auctions/<int:auction_id>/bid", methods=["POST"])
@login_required
def submit_bid(auction_id):
    """商品詳細内の入札フォームを受け付ける。"""
    try:
        amount = int(request.form.get("amount", -1))
        expected_raw = request.form.get("expected_price")
        expected_price = int(expected_raw) if expected_raw not in (None, "") else None
    except ValueError:
        amount, expected_price = -1, None
    try:
        auction_service.place_bid(
            auction_id, current_user, amount, expected_price=expected_price
        )
        flash(f"{amount}pt で入札しました。", "info")
        # 他人の入札に応じて自動入札を判定する
        auction_service.process_auto_bids(auction_id)
    except PriceChangedError as exc:
        # 手動入札確認後に価格が変わった場合は再確認を求める
        flash(f"{exc}（最新価格: {exc.current_price}pt）", "error")
    except InsufficientPointsError:
        flash(
            "ポイント残高が不足しています。チャージ画面は Ver0.5 では課金未提供です。",
            "error",
        )
        return redirect(url_for("points.show_charge"))
    except AuctionError as exc:
        flash(str(exc), "error")
    return redirect(url_for("auctions.show_auction_detail", auction_id=auction_id))


@bp.route("/auctions/<int:auction_id>/auto-bid", methods=["POST"])
@login_required
def set_auto_bid(auction_id):
    """ログインユーザーの自動入札上限額を受け付ける。"""
    try:
        max_amount = int(request.form.get("max_amount", -1))
    except ValueError:
        max_amount = -1
    try:
        auction_service.configure_auto_bid(auction_id, current_user, max_amount)
        flash(f"自動入札の上限を {max_amount}pt に設定しました。", "info")
    except AuctionError as exc:
        flash(str(exc), "error")
    return redirect(url_for("auctions.show_auction_detail", auction_id=auction_id))


@bp.route("/auctions/<int:auction_id>/auto-bid/stop", methods=["POST"])
@login_required
def stop_auto_bid(auction_id):
    """本人の設定を停止する。受理済み入札は取り消さない。"""
    try:
        auction_service.stop_auto_bid(auction_id, current_user)
        flash("自動入札を停止しました。受理済みの入札は維持されます。", "info")
    except AuctionError as exc:
        flash(str(exc), "error")
    return redirect(url_for("auctions.show_auction_detail", auction_id=auction_id))
