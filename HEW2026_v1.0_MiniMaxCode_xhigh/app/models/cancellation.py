"""取消・非公開の操作履歴。

作品・競売・入札の履歴は削除しない。操作の事実だけを残す。
"""

from __future__ import annotations

from app.extensions import db
from app.utils import utcnow

ACTION_SELLER_CANCEL = "seller_cancel"
ACTION_ADMIN_CANCEL = "admin_cancel"
ACTION_HIDE = "hide"
ACTION_RESTORE = "restore"


class AuctionCancellation(db.Model):
    """取消・非公開化・公開復帰の操作履歴。"""

    __tablename__ = "auction_cancellations"

    id = db.Column(db.Integer, primary_key=True)
    auction_id = db.Column(
        db.Integer, db.ForeignKey("auctions.id"), nullable=True, index=True
    )
    artwork_id = db.Column(
        db.Integer, db.ForeignKey("artworks.id"), nullable=False, index=True
    )
    action = db.Column(db.String(30), nullable=False, index=True)
    actor_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    reason = db.Column(db.String(300), nullable=True)
    refunded_points = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(
        db.DateTime, nullable=False, default=utcnow, index=True
    )

    actor = db.relationship("User", foreign_keys=[actor_id])

    def __repr__(self) -> str:  # pragma: no cover - デバッグ用
        return f"<AuctionCancellation {self.id} {self.action}>"
