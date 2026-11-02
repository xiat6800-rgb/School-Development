"""ユーザー模型。

仕様決定事項1章により、メールアドレスは一切使わない。
表示名はユーザー名とは別管理し、復旧コードはハッシュで保存する。
"""

from __future__ import annotations

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.utils import utcnow


class User(UserMixin, db.Model):
    """サイト利用者。"""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True, index=True)
    disp_name = db.Column(db.String(50), nullable=False)
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

    # --- パスワード ---
    def set_password(self, raw_password: str) -> None:
        """入力された平文パスワードをハッシュ化して保存する。"""
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        """入力された平文パスワードと保存済みハッシュを照合する。"""
        return check_password_hash(self.password_hash, raw_password)

    # --- 復旧コード ---
    def set_recovery_code(self, code: str) -> None:
        """復旧コードをハッシュ化して保存する。旧コードは無効化する。"""
        self.recovery_code_hash = generate_password_hash(code)
        self.recovery_code_used_at = None

    def check_recovery_code(self, code: str) -> bool:
        """復旧コードを照合する。未設定なら常に False。"""
        if not self.recovery_code_hash:
            return False
        return check_password_hash(self.recovery_code_hash, code)

    def invalidate_recovery_code(self) -> None:
        """使用済み・失効済みの復旧コードを無効化する。"""
        self.recovery_code_hash = None
        self.recovery_code_used_at = utcnow()

    @property
    def is_admin(self) -> bool:
        """管理者権限を持つかを返す。"""
        return self.role == "admin"

    def __repr__(self) -> str:  # pragma: no cover - デバッグ用
        return f"<User {self.id} {self.username}>"
