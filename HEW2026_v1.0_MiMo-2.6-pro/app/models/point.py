from app.extensions import db


class WalletTransaction(db.Model):
    __tablename__ = "wallet_transactions"

    TYPE_BONUS = "bonus"
    TYPE_BID = "bid"
    TYPE_REFUND = "refund"
    TYPE_SALE = "sale"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    transaction_type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    balance_after = db.Column(db.Integer, nullable=False)
    related_auction_id = db.Column(
        db.Integer, db.ForeignKey("auctions.id"), nullable=True, index=True
    )
    related_bid_id = db.Column(
        db.Integer, db.ForeignKey("bids.id"), nullable=True, index=True
    )
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    user = db.relationship(
        "User", backref=db.backref("wallet_transactions", lazy="dynamic")
    )


class BonusGrant(db.Model):
    """ボーナス付与の重複防止台帳。同一 (user, type, period_key) は1回だけ。"""

    __tablename__ = "bonus_grants"
    __table_args__ = (
        db.UniqueConstraint(
            "user_id", "bonus_type", "period_key", name="uq_bonus_grant"
        ),
    )

    TYPE_REGISTER = "register"
    TYPE_FIRST_LISTING = "first_listing"
    TYPE_DRAWING_SAVE = "drawing_save"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    bonus_type = db.Column(db.String(20), nullable=False)
    period_key = db.Column(db.String(20), nullable=False, default="")
    amount = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    user = db.relationship("User", backref=db.backref("bonus_grants", lazy="dynamic"))
