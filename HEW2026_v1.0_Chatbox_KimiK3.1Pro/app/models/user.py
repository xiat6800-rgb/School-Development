from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.utils import utcnow


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(50), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    recovery_code_hash = db.Column(db.String(255), nullable=True)
    recovery_code_used_at = db.Column(db.DateTime, nullable=True)
    role = db.Column(db.String(20), nullable=False, default="user")
    point_balance = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    artworks = db.relationship("Artwork", back_populates="artist", lazy="dynamic")

    @property
    def is_admin(self):
        return self.role == "admin"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def set_recovery_code(self, code):
        self.recovery_code_hash = generate_password_hash(code)
        self.recovery_code_used_at = None

    def check_recovery_code(self, code):
        return bool(
            self.recovery_code_hash
            and self.recovery_code_used_at is None
            and check_password_hash(self.recovery_code_hash, code)
        )


class WalletTransaction(db.Model):
    __tablename__ = "wallet_transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    transaction_type = db.Column(db.String(30), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    balance_after = db.Column(db.Integer, nullable=False)
    auction_id = db.Column(db.Integer, db.ForeignKey("auctions.id"), nullable=True)
    bid_id = db.Column(db.Integer, db.ForeignKey("bids.id"), nullable=True)
    dedupe_key = db.Column(db.String(160), unique=True, nullable=False)
    note = db.Column(db.String(200), nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User", backref=db.backref("wallet_transactions", lazy="dynamic"))
    auction = db.relationship("Auction")
    bid = db.relationship("Bid")


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    notification_type = db.Column(db.String(40), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    auction_id = db.Column(db.Integer, db.ForeignKey("auctions.id"), nullable=True)
    dedupe_key = db.Column(db.String(180), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User", backref=db.backref("notifications", lazy="dynamic"))
    auction = db.relationship("Auction")
