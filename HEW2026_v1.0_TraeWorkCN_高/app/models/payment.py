"""payment_intents（Ver0.5 では画面遷移用の記録のみ。Stripe 連携なし）。"""
from app.extensions import db
from app.models.types import ID_TYPE
from app.utils import utcnow


class PaymentIntent(db.Model):
    __tablename__ = "payment_intents"
    __table_args__ = (
        db.Index("idx_payment_intents_user", "user_id"),
        db.Index("idx_payment_intents_auction", "auction_id"),
        db.Index("idx_payment_intents_status", "status"),
    )

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    user_id = db.Column(ID_TYPE, db.ForeignKey("users.id"), nullable=False)
    auction_id = db.Column(
        ID_TYPE, db.ForeignKey("auctions.id"), nullable=True
    )
    amount = db.Column(db.Integer, nullable=False)
    status = db.Column(
        db.Enum(
            "pending", "succeeded", "failed", "cancelled", name="payment_intent_status"
        ),
        nullable=False,
        default="pending",
    )
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    user = db.relationship(
        "User", backref=db.backref("payment_intents", lazy="dynamic")
    )
    auction = db.relationship(
        "Auction", backref=db.backref("payment_intents", lazy="dynamic")
    )
