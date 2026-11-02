"""アカウント画面（本人専用の情報一覧）。"""

from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.account import account_bp
from app.extensions import db
from app.models.auto_bid import AutoBidSetting
from app.models.favorite import ArtworkFavorite, AuctionFavorite
from app.services import auth_service
from app.services.errors import ServiceError
from app.services.point_service import list_point_transactions

TABS = ("drafts", "listings", "favorites", "auto-bids", "points")


@account_bp.route("/account/")
@login_required
def show_account():
    """本人のアカウント画面を表示する。"""
    tab = request.args.get("tab", "drafts")
    if tab not in TABS:
        tab = "drafts"

    drafts = []
    listings = []
    artwork_favorites = []
    auction_favorites = []
    auto_bids = []
    transactions = []

    if tab == "drafts":
        from app.services.artwork_service import list_user_drafts

        drafts = list_user_drafts(current_user)
    elif tab == "listings":
        from app.services.artwork_service import list_user_listings

        listings = list_user_listings(current_user)
    elif tab == "favorites":
        artwork_favorites = (
            ArtworkFavorite.query.filter_by(user_id=current_user.id)
            .order_by(ArtworkFavorite.created_at.desc())
            .all()
        )
        auction_favorites = (
            AuctionFavorite.query.filter_by(user_id=current_user.id)
            .order_by(AuctionFavorite.created_at.desc())
            .all()
        )
    elif tab == "auto-bids":
        auto_bids = (
            AutoBidSetting.query.filter_by(user_id=current_user.id)
            .order_by(AutoBidSetting.created_at.desc())
            .all()
        )
    elif tab == "points":
        transactions = list_point_transactions(current_user)

    return render_template(
        "account/index.html",
        tab=tab,
        drafts=drafts,
        listings=listings,
        artwork_favorites=artwork_favorites,
        auction_favorites=auction_favorites,
        auto_bids=auto_bids,
        transactions=transactions,
    )


@account_bp.route("/account/display-name", methods=["POST"])
@login_required
def update_display_name():
    """本人の表示名を更新する。"""
    disp_name = (request.form.get("disp_name") or "").strip()
    if not disp_name:
        flash("表示名を入力してください。", "error")
        return redirect(url_for("account.show_account"))
    current_user.disp_name = disp_name[:50]
    db.session.commit()
    flash("表示名を更新しました。", "success")
    return redirect(url_for("account.show_account", tab="drafts"))


@account_bp.route("/account/recovery-code", methods=["POST"])
@login_required
def regenerate_recovery_code():
    """現在のパスワードを確認して復旧コードを再発行する。"""
    password = request.form.get("password", "")
    try:
        code = auth_service.regenerate_recovery_code(current_user, password)
    except ServiceError as error:
        flash(error.message, "error")
        return redirect(url_for("account.show_account"))

    db.session.commit()
    return render_template(
        "auth/recovery_code.html", recovery_code=code, is_first_time=False
    )
