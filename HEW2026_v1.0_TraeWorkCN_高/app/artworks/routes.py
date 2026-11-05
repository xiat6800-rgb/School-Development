"""描画・PNG 保存・下書き・出品設定（要件定義書 5.2〜5.3）。"""
import os

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import select

from app.artworks.forms import ArtworkInfoForm, ListingForm
from app.extensions import db
from app.models import Artwork, Auction, Tag
from app.services import bonus_service, image_service
from app.utils import from_jst_input, utcnow

bp = Blueprint("artworks", __name__, url_prefix="/artworks")

TIME_LIMITS = [(10, "10秒"), (30, "30秒"), (60, "1分"), (300, "5分")]


def _owned_artwork(artwork_id):
    artwork = db.session.get(Artwork, artwork_id)
    if artwork is None:
        abort(404)
    if artwork.seller_id != current_user.id:
        abort(403)
    return artwork


def _tag_choices(form):
    tags = db.session.execute(select(Tag).order_by(Tag.id.asc())).scalars().all()
    form.tags.choices = [(tag.id, tag.name) for tag in tags]
    return tags


@bp.route("/draw")
@login_required
def draw():
    return render_template(
        "artworks/draw.html",
        time_limits=TIME_LIMITS,
        canvas_width=current_app.config["CANVAS_WIDTH"],
        canvas_height=current_app.config["CANVAS_HEIGHT"],
        draw_bonus=current_app.config["BONUS_DRAW_POINTS"],
        draw_bonus_times=bonus_service.remaining_draw_bonus_times(current_user),
    )


@bp.route("/draw", methods=["POST"])
@login_required
def save_draft():
    image_data = request.form.get("image_data", "")
    try:
        filename = image_service.save_png_data_url(
            image_data,
            current_app.config["UPLOAD_FOLDER"],
            current_app.config["MAX_IMAGE_BYTES"],
            current_app.config["MAX_IMAGE_WIDTH"],
            current_app.config["MAX_IMAGE_HEIGHT"],
        )
    except image_service.ImageValidationError as exc:
        flash(str(exc), "error")
        return redirect(url_for("artworks.draw"))

    artwork = Artwork(
        seller_id=current_user.id,
        title="無題",
        description=None,
        image_path=filename,
        status="draft",
    )
    db.session.add(artwork)
    db.session.flush()
    bonus_service.grant_draw_bonus(current_user)
    db.session.commit()

    flash("絵を下書きとして保存しました。保存後の加筆はできません。", "success")
    return redirect(url_for("account.index", tab="drafts"))


@bp.route("/<int:artwork_id>/image")
def image(artwork_id):
    artwork = db.session.get(Artwork, artwork_id)
    if artwork is None:
        abort(404)
    # 下書きは作者だけが閲覧できる（要件定義書 5.2 / 7.3）
    if artwork.status == "draft":
        if not current_user.is_authenticated or current_user.id != artwork.seller_id:
            abort(403)

    filename = os.path.basename(artwork.image_path)
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    if not os.path.isfile(path):
        abort(404)
    return send_file(path, mimetype="image/png", max_age=0)


@bp.route("/<int:artwork_id>/listing", methods=["GET", "POST"])
@login_required
def listing(artwork_id):
    artwork = _owned_artwork(artwork_id)
    if artwork.status != "draft" or artwork.auction is not None:
        flash("この作品はすでに出品されています。", "warning")
        return redirect(url_for("account.index", tab="listings"))

    form = ListingForm()
    _tag_choices(form)
    if request.method == "GET":
        form.title.data = artwork.title if artwork.title != "無題" else ""

    if form.validate_on_submit():
        end_time = from_jst_input(form.end_time.data.strip())
        if end_time is None:
            flash("終了日時の形式が正しくありません。", "error")
        elif end_time <= utcnow():
            flash("終了日時は現在より後の日時にしてください。", "error")
        else:
            artwork.title = form.title.data.strip()
            artwork.description = (form.description.data or "").strip() or None
            artwork.tags = (
                db.session.execute(
                    select(Tag).where(Tag.id.in_(form.tags.data or []))
                )
                .scalars()
                .all()
            )

            auction = Auction(
                artwork_id=artwork.id,
                start_price=form.start_price.data,
                current_price=form.start_price.data,
                status="active",
                start_time=utcnow(),
                end_time=end_time,
            )
            db.session.add(auction)
            artwork.status = "listed"
            db.session.flush()

            bonus_service.grant_listing_bonus(current_user, auction.id)
            db.session.commit()

            flash("出品しました。オークションが開始されています。", "success")
            return redirect(url_for("auctions.detail", auction_id=auction.id))

    return render_template("artworks/listing.html", form=form, artwork=artwork)


@bp.route("/<int:artwork_id>/edit", methods=["GET", "POST"])
@login_required
def edit_info(artwork_id):
    artwork = _owned_artwork(artwork_id)
    if artwork.status in {"sold", "cancelled"}:
        flash("この作品の出品情報は編集できません。", "warning")
        return redirect(url_for("account.index", tab="listings"))

    form = ArtworkInfoForm(obj=artwork)
    _tag_choices(form)
    if request.method == "GET":
        form.tags.data = [tag.id for tag in artwork.tags]

    if form.validate_on_submit():
        artwork.title = form.title.data.strip()
        artwork.description = (form.description.data or "").strip() or None
        artwork.tags = (
            db.session.execute(
                select(Tag).where(Tag.id.in_(form.tags.data or []))
            )
            .scalars()
            .all()
        )
        db.session.commit()
        flash("出品情報を更新しました。絵の加筆はできません。", "success")
        return redirect(url_for("account.index", tab="drafts" if artwork.status == "draft" else "listings"))

    return render_template("artworks/edit_info.html", form=form, artwork=artwork)
