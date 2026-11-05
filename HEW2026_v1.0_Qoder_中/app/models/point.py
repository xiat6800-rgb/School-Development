"""ポイント取引履歴とボーナス付与履歴（重複防止用）。"""
from datetime import datetime, timezone

from ..extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class WalletTransaction(db.Model):
    __tablename__ = "wallet_transactions"

    id = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'), primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id"), nullable=False, index=True
    )
    # charge / bid / refund / purchase / bonus
    transaction_type = db.Column(db.String(10), nullable=False)
    # 増加は正、減少は負
    amount = db.Column(db.Integer, nullable=False)
    balance_after = db.Column(db.Integer, nullable=False)
    related_auction_id = db.Column(db.BigInteger, nullable=True)
    related_bid_id = db.Column(db.BigInteger, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User", backref="wallet_transactions")

    __table_args__ = (
        db.Index("idx_wallet_user_created", "user_id", "created_at"),
    )


class BonusGrant(db.Model):
    """ボーナス付与の履歴。grant_key の一意制約で再送時の重複付与を防ぐ。"""

    __tablename__ = "bonus_grants"

    id = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'), primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id"), nullable=False, index=True
    )
    # signup:{user_id} / first_listing:{user_id} / draw_save:{user_id}:{jst日付}
    grant_key = db.Column(db.String(100), unique=True, nullable=False)
    bonus_type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User", backref="bonus_grants")
