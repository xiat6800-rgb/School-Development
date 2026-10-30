"""ユーザーモデル。認証はユーザー名とパスワード、復旧は復旧コードで行う。"""

import secrets

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from ..clock import utcnow
from ..constants import ROLE_ADMIN, ROLE_USER
from ..extensions import db, login_manager

RECOVERY_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_recovery_code():
    """復旧コード（XXXX-XXXX-XXXX）を生成する。"""
    groups = [
        "".join(secrets.choice(RECOVERY_CODE_ALPHABET) for _ in range(4))
        for _ in range(3)
    ]
    return "-".join(groups)


class User(UserMixin, db.Model):
    """利用者。メールアドレスは保持しない。"""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False, index=True)
    disp_name = db.Column(db.String(50), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    recovery_code_hash = db.Column(db.String(255))
    recovery_code_issued_at = db.Column(db.DateTime)
    recovery_code_active = db.Column(db.Boolean, nullable=False, default=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_USER)
    point_balance = db.Column(db.Integer, nullable=False, default=0)
    is_active_flag = db.Column("is_active", db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    @property
    def is_active(self):
        """Flask-Login 用。無効化した利用者はログインさせない。"""
        return bool(self.is_active_flag)

    def set_password(self, raw_password):
        """パスワードをハッシュ化して保存する。"""
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        """入力パスワードを照合する。"""
        if not raw_password:
            return False
        return check_password_hash(self.password_hash, raw_password)

    def issue_recovery_code(self):
        """復旧コードを発行し、ハッシュだけを保存して平文を1度返す。"""
        raw_code = generate_recovery_code()
        self.recovery_code_hash = generate_password_hash(raw_code)
        self.recovery_code_issued_at = utcnow()
        self.recovery_code_active = True
        return raw_code

    @property
    def has_active_recovery_code(self):
        return bool(self.recovery_code_hash) and bool(self.recovery_code_active)

    def verify_recovery_code(self, raw_code):
        """復旧コードを照合する。無効化済みなら常に False。"""
        if not self.has_active_recovery_code or not raw_code:
            return False
        return check_password_hash(
            self.recovery_code_hash, raw_code.strip().upper()
        )

    def invalidate_recovery_code(self):
        """使用済みの復旧コードを無効にする。"""
        self.recovery_code_active = False

    def is_admin(self):
        return self.role == ROLE_ADMIN

    def __repr__(self):
        return f"<User {self.username}>"


@login_manager.user_loader
def load_user(user_id):
    """Flask-Login のコールバック。ユーザーIDから利用者を取得する。"""
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None
