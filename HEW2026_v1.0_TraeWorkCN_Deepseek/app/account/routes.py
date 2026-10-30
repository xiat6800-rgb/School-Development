"""アカウント画面（下書き・出品・お気に入り・自動入札・ポイント履歴）。"""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from app.models import (
    Artwork,
    ArtworkBookmark,
    AutoBidSetting,
    Bookmark,
    WalletTransaction,
)
from app.services import auction_service

bp = Blueprint("account", __name__, url_prefix="/account")

TABS = (
    "drafts",
    "listings",
    "favorites_artworks",
    "favorites_auctions",
    "auto_bids",
    "wallet",
)


@bp.route("/")
@login_required
def index():
    tab = request.args.get("tab", "drafts")
    if tab not in TABS:
        tab = "drafts"

    drafts = (
        db.session.execute(
            select(Artwork)
            .where(Artwork.seller_id == current_user.id, Artwork.status == "draft")
            .order_by(Artwork.created_at.desc())
        )
        .scalars()
        .all()
    )
    listings = (
        db.session.execute(
            select(Artwork)
            .where(
                Artwork.seller_id == current_user.id,
                Artwork.status.in_(["listed", "sold"]),
            )
            .order_by(Artwork.created_at.desc())
        )
        .scalars()
        .all()
    )
    favorite_artworks = (
        db.session.execute(
            select(ArtworkBookmark)
            .where(ArtworkBookmark.user_id == current_user.id)
            .order_by(ArtworkBookmark.created_at.desc())
        )
        .scalars()
        .all()
    )
    favorite_auctions = (
        db.session.execute(
            select(Bookmark)
            .where(Bookmark.user_id == current_user.id)
            .order_by(Bookmark.created_at.desc())
        )
        .scalars()
        .all()
    )
    auto_bids = (
        db.session.execute(
            select(AutoBidSetting)
            .where(AutoBidSetting.user_id == current_user.id)
            .order_by(AutoBidSetting.created_at.desc())
        )
        .scalars()
        .all()
    )
    wallet = (
        db.session.execute(
            select(WalletTransaction)
            .where(WalletTransaction.user_id == current_user.id)
            .order_by(WalletTransaction.created_at.desc())
            .limit(50)
        )
        .scalars()
        .all()
    )

    return render_template(
        "account/index.html",
        tab=tab,
        drafts=drafts,
        listings=listings,
        favorite_artworks=favorite_artworks,
        favorite_auctions=favorite_auctions,
        auto_bids=auto_bids,
        wallet=wallet,
    )


@bp.route("/profile", methods=["POST"])
@login_required
def update_profile():
    disp_name = (request.form.get("disp_name") or "").strip()
    if not disp_name or len(disp_name) > 50:
        flash("表示名は1〜50文字で入力してください。", "error")
    else:
        current_user.disp_name = disp_name
        db.session.commit()
        flash("表示名を更新しました。", "success")
    return redirect(url_for("account.index"))


@bp.route("/auto-bid/<int:setting_id>/stop", methods=["POST"])
@login_required
def stop_auto_bid(setting_id):
    if auction_service.stop_auto_bid(setting_id, current_user.id):
        flash("自動入札を停止しました。", "info")
    else:
        flash("自動入札の設定が見つかりません。", "error")
    return redirect(url_for("account.index", tab="auto_bids"))
