"""自動入札設定の模型。

上限額は確保せず、実際に入札した額だけを消費する。
"""

from __future__ import annotations

from app.extensions import db
from app.utils import utcnow


class AutoBidSetting(db.Model):
    """1 ユーザー 1 オークション分の自動入札設定。"""

    __tablename__ = "auto_bid_settings"
    __table_args__ = (
        db.UniqueConstraint("auction_id", "user_id", name="uq_auto_bid_auction_user"),
    )

    id = db.Column(db.Integer, primary_key=True)
    auction_id = db.Column(
        db.Integer, db.ForeignKey("auctions.id"), nullable=False, index=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    max_amount = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    user = db.relationship("User", backref="auto_bid_settings")
    auction = db.relationship("Auction", backref="auto_bid_settings")

    def __repr__(self) -> str:  # pragma: no cover - デバッグ用
        return f"<AutoBidSetting {self.id} max={self.max_amount}>"
