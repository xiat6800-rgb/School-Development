from flask import render_template

from app.extensions import db
from app.main import bp
from app.models import Artwork, Auction, LiveStream, Tag
from app.services.auction_service import close_expired_auctions
from app.services.stream_service import close_stale_streams


@bp.get("/")
def index():
    if close_expired_auctions():
        db.session.commit()
    close_stale_streams()
    db.session.commit()
    auctions = Auction.query.join(Artwork).filter(
        Auction.status == "active", Artwork.is_public.is_(True)
    ).order_by(Auction.ends_at).limit(12).all()
    streams = LiveStream.query.filter(
        LiveStream.status.in_(("live", "paused"))
    ).order_by(LiveStream.started_at.desc()).limit(6).all()
    recent = Auction.query.join(Artwork).filter(
        Auction.status == "ended", Artwork.is_public.is_(True)
    ).order_by(Auction.settled_at.desc()).limit(4).all()
    tags = Tag.query.order_by(Tag.name).all()
    return render_template(
        "main/index.html", auctions=auctions, streams=streams, recent=recent, tags=tags
    )
