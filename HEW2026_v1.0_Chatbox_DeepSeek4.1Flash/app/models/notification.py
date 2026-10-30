"""アプリ内通知モデル。メール配信は行わない。"""

from ..clock import utcnow
from ..extensions import db


class Notification(db.Model):
    """利用者ごとのアプリ内通知。"""

    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    notification_type = db.Column(db.String(30), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    related_auction_id = db.Column(db.Integer, db.ForeignKey("auctions.id"), index=True)
    related_bid_id = db.Column(db.Integer, db.ForeignKey("bids.id"))
    # 再実行時の重複生成を防ぐキー
    dedupe_key = db.Column(db.String(120), unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    user = db.relationship("User", backref=db.backref("notifications", lazy="dynamic"))
    auction = db.relationship("Auction", foreign_keys=[related_auction_id])

    def __repr__(self):
        return f"<Notification {self.id} {self.notification_type}>"
