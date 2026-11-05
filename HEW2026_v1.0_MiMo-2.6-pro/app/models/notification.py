from app.extensions import db


class Notification(db.Model):
    __tablename__ = "notifications"

    TYPE_BID_RECEIVED = "bid_received"
    TYPE_OUTBID = "outbid"
    TYPE_AUCTION_WON = "auction_won"
    TYPE_AUCTION_SOLD = "auction_sold"
    TYPE_AUCTION_UNSOLD = "auction_unsold"
    TYPE_AUTO_BID_STOPPED = "auto_bid_stopped"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    notification_type = db.Column(db.String(30), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    related_auction_id = db.Column(
        db.Integer, db.ForeignKey("auctions.id"), nullable=True, index=True
    )
    related_bid_id = db.Column(
        db.Integer, db.ForeignKey("bids.id"), nullable=True
    )
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    user = db.relationship(
        "User", backref=db.backref("notifications", lazy="dynamic")
    )
