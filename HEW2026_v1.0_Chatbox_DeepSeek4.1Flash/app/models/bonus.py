"""ボーナス付与の履歴モデル。再送による重複付与を防ぐ。"""

from ..clock import utcnow
from ..extensions import db


class BonusGrant(db.Model):
    """ボーナスの付与記録。grant_key の一意制約で二重付与を防ぐ。"""

    __tablename__ = "bonus_grants"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    bonus_type = db.Column(db.String(30), nullable=False)
    grant_key = db.Column(db.String(80), unique=True, nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    transaction_id = db.Column(db.Integer, db.ForeignKey("wallet_transactions.id"))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User", backref=db.backref("bonus_grants", lazy="dynamic"))
    transaction = db.relationship("WalletTransaction")

    def __repr__(self):
        return f"<BonusGrant {self.grant_key} {self.amount}>"
