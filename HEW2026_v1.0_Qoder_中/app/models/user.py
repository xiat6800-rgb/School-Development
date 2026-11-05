"""ユーザーモデル。ユーザー名認証・メール不使用（仕様決定事項 1章）。"""
from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'), primary_key=True, autoincrement=True)
    username = db.Column(db.String(20), unique=True, nullable=False, index=True)
    disp_name = db.Column(db.String(50), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    # 復旧コードはハッシュだけ保存。使用・再発行で無効化（NULL）する
    recovery_code_hash = db.Column(db.String(255), nullable=True)
    role = db.Column(db.String(10), nullable=False, default="user")
    point_balance = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def set_recovery_code(self, plain_code):
        self.recovery_code_hash = generate_password_hash(plain_code)

    def check_recovery_code(self, plain_code):
        if not self.recovery_code_hash or not plain_code:
            return False
        return check_password_hash(self.recovery_code_hash, plain_code)

    def invalidate_recovery_code(self):
        self.recovery_code_hash = None

    @property
    def is_admin(self):
        return self.role == "admin"
