"""ホーム画面（公開作品の一覧とタグへの入口）。"""
from flask import Blueprint, redirect, render_template, url_for
from sqlalchemy import func, select

from app.extensions import db
from app.models import Artwork, Auction, Tag, User

bp = Blueprint("main", __name__)


@bp.route("/favicon.ico")
def favicon():
    return redirect(url_for("static", filename="favicon.svg"), code=301)


@bp.route("/")
def home():
    artworks = (
        db.session.execute(
            select(Artwork)
            .where(Artwork.status.in_(["listed", "sold"]))
            .order_by(Artwork.created_at.desc())
            .limit(12)
        )
        .scalars()
        .all()
    )
    tags = db.session.execute(select(Tag).order_by(Tag.id.asc())).scalars().all()
    stats = {
        "artworks": db.session.query(func.count(Artwork.id)).scalar() or 0,
        "auctions": db.session.query(func.count(Auction.id))
        .filter(Auction.status == "active")
        .scalar()
        or 0,
        "users": db.session.query(func.count(User.id)).scalar() or 0,
    }
    return render_template("main/home.html", artworks=artworks, tags=tags, stats=stats)
