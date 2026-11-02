"""商品詳細画面と入札。

入札は専用画面を設けず、商品詳細画面内で「入力 → 確認 → 確定」を行う。
確認済みの价格为現在の価格から変わっている場合、再確認を求める。
"""

from __future__ import annotations

from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.auctions import auctions_bp
from app.extensions import db
from app.models.auto_bid import AutoBidSetting
from app.services import auction_service
from app.services.errors import ServiceError
from app.utils import format_jst, utcnow


@auctions_bp.route("/auctions/<int:auction_id>")
def show_auction_detail(auction_id: int):
    """オークションIDで作品・価格・履歴・入札結果を表示する。"""
    auction = auction_service.get_auction(auction_id)
    artwork = auction.artwork
    bids = auction.accepted_bids()
    top_bid = bids[0] if bids else None

    auto_bid = None
    if current_user.is_authenticated:
        auto_bid = AutoBidSetting.query.filter_by(
            auction_id=auction.id, user_id=current_user.id
        ).first()

    is_seller = (
        current_user.is_authenticated and artwork.artist_id == current_user.id
    )
    return render_template(
        "auctions/detail.html",
        auction=auction,
        artwork=artwork,
        bids=bids,
        top_bid=top_bid,
        auto_bid=auto_bid,
        is_seller=is_seller,
        min_bid_amount=auction.current_price
        + int(current_app.config["BID_MIN_INCREMENT"]),
        confirm_bid_amount=None,
        end_time_label=format_jst(auction.end_time, "%Y/%m/%d %H:%M"),
        is_expired=utcnow() >= auction.end_time,
    )


@auctions_bp.route("/auctions/<int:auction_id>/bid", methods=["POST"])
@login_required
def submit_bid(auction_id: int):
    """入札フォームを受け取る（確認 → 確定の 2 段階）。"""
    auction = auction_service.get_auction(auction_id)
    artwork = auction.artwork

    raw_amount = (request.form.get("bid_amount") or "").strip()
    confirmed = request.form.get("confirmed") == "1"
    raw_expected = (request.form.get("expected_price") or "").strip()

    try:
        amount = int(raw_amount)
    except ValueError:
        flash("入札額を入力してください。", "error")
        return redirect(url_for("auctions.show_auction_detail", auction_id=auction.id))

    if not confirmed:
        # 確認段階：状態を書き換えず、確認用の表示を返す
        return render_template(
            "auctions/detail.html",
            auction=auction,
            artwork=artwork,
            bids=auction.accepted_bids(),
            top_bid=auction.top_bid(),
            auto_bid=AutoBidSetting.query.filter_by(
                auction_id=auction.id, user_id=current_user.id
            ).first(),
            is_seller=artwork.artist_id == current_user.id,
            min_bid_amount=auction.current_price
            + int(current_app.config["BID_MIN_INCREMENT"]),
            confirm_bid_amount=amount,
            end_time_label=format_jst(auction.end_time, "%Y/%m/%d %H:%M"),
            is_expired=utcnow() >= auction.end_time,
        )

    expected_price = None
    if raw_expected:
        try:
            expected_price = int(raw_expected)
        except ValueError:
            expected_price = None

    try:
        bid = auction_service.place_bid(
            auction.id,
            current_user,
            amount,
            expected_price=expected_price,
        )
        auction_service.process_auto_bids(auction)
        db.session.commit()
    except ServiceError as error:
        db.session.rollback()
        flash(error.message, "error")
        return redirect(url_for("auctions.show_auction_detail", auction_id=auction.id))

    flash(f"{bid.bid_amount}pt で入札を受け付けました。", "success")
    return redirect(url_for("auctions.show_auction_detail", auction_id=auction.id))


@auctions_bp.route("/auctions/<int:auction_id>/auto-bid", methods=["POST"])
@login_required
def set_auto_bid(auction_id: int):
    """自動入札の上限額を受け取る。"""
    auction = auction_service.get_auction(auction_id)
    try:
        auction_service.configure_auto_bid(
            current_user, auction, request.form.get("max_amount")
        )
        db.session.commit()
    except ServiceError as error:
        db.session.rollback()
        flash(error.message, "error")
        return redirect(url_for("auctions.show_auction_detail", auction_id=auction.id))

    flash("自動入札を設定しました。", "success")
    return redirect(url_for("auctions.show_auction_detail", auction_id=auction.id))


@auctions_bp.route("/auctions/<int:auction_id>/auto-bid/stop", methods=["POST"])
@login_required
def stop_auto_bid(auction_id: int):
    """自動入札を停止する。受理済み入札は取り消さない。"""
    auction = auction_service.get_auction(auction_id)
    try:
        auction_service.stop_auto_bid(current_user, auction)
        db.session.commit()
    except ServiceError as error:
        db.session.rollback()
        flash(error.message, "error")
        return redirect(url_for("auctions.show_auction_detail", auction_id=auction.id))

    flash("自動入札を停止しました。", "success")
    return redirect(url_for("auctions.show_auction_detail", auction_id=auction.id))
