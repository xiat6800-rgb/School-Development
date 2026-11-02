"""ポイント取引履歴とボーナス付与記録の模型。"""

from __future__ import annotations

from app.extensions import db
from app.utils import utcnow

TYPE_BID = "bid"
TYPE_REFUND = "refund"
TYPE_SALE = "sale"
TYPE_BONUS = "bonus"

BONUS_SIGNUP = "signup"
BONUS_FIRST_LISTING = "first_listing"
BONUS_DRAW = "draw"


class WalletTransaction(db.Model):
    """ポイント残高の変更履歴。

    残高は負にしない。増減と同じトランザクションで記録する。
    """

    __tablename__ = "wallet_transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    transaction_type = db.Column(db.String(20), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)
    balance_after = db.Column(db.Integer, nullable=False)
    related_auction_id = db.Column(
        db.Integer, db.ForeignKey("auctions.id"), nullable=True, index=True
    )
    related_bid_id = db.Column(
        db.Integer, db.ForeignKey("bids.id"), nullable=True
    )
    # 同一キーの再実行で台帳に 2 行目を追加しないための一意キー。
    reference_key = db.Column(
        db.String(120), nullable=True, unique=True, index=True
    )
    reason = db.Column(db.String(300), nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=utcnow, index=True
    )

    user = db.relationship("User", backref="transactions")


class BonusGrant(db.Model):
    """ボーナス付与の記録。同一条件の重複付与を防ぐ。"""

    __tablename__ = "bonus_grants"
    __table_args__ = (
        db.UniqueConstraint(
            "user_id", "bonus_type", "bonus_date", name="uq_bonus_grant"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    bonus_type = db.Column(db.String(30), nullable=False)
    bonus_date = db.Column(db.String(10), nullable=False, default="once")
    amount = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
