from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.admin import bp
from app.extensions import db
from app.models import Artwork, Auction
from app.services.cancellation_service import (
    cancel_auction, hide_artwork, restore_artwork_visibility,
)
from app.services.comment_service import admin_visible_body, get_comment_audit
from app.utils import admin_required


@bp.get("")
@login_required
@admin_required
def dashboard():
    auctions = Auction.query.order_by(Auction.id.desc()).limit(80).all()
    artworks = Artwork.query.order_by(Artwork.id.desc()).limit(80).all()
    return render_template("admin/dashboard.html", auctions=auctions, artworks=artworks)


@bp.post("/auctions/<int:auction_id>/cancel")
@login_required
@admin_required
def cancel_auction_as_admin(auction_id):
    cancel_auction(
        auction_id, current_user, reason=request.form.get("reason", ""), as_admin=True
    )
    db.session.commit()
    flash("取消・未返還分の返還・自動入札停止を完了しました。", "success")
    return redirect(request.referrer or url_for("admin.dashboard"))


@bp.post("/artworks/<int:artwork_id>/hide")
@login_required
@admin_required
def hide_artwork_route(artwork_id):
    hide_artwork(artwork_id, current_user, request.form.get("reason", ""))
    db.session.commit()
    flash("作品を非公開にしました。旧競売は再開されません。", "success")
    return redirect(url_for("admin.dashboard"))


@bp.post("/artworks/<int:artwork_id>/restore")
@login_required
@admin_required
def restore_artwork_visibility_route(artwork_id):
    restore_artwork_visibility(artwork_id, current_user, request.form.get("reason", ""))
    db.session.commit()
    flash("作品の公開を戻しました。再出品条件は通常どおり適用されます。", "success")
    return redirect(url_for("admin.dashboard"))


@bp.get("/comments")
@login_required
@admin_required
def show_comment_audit():
    return render_template(
        "admin/comments.html", audits=get_comment_audit(),
        admin_visible_body=admin_visible_body,
    )
