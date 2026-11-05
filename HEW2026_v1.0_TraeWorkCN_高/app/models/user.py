"""users テーブル。"""
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.types import ID_TYPE
from app.utils import utcnow


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    disp_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(225), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(
        db.Enum("user", "admin", name="user_role"), nullable=False, default="user"
    )
    point_balance = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    def set_password(self, raw_password):
        # Werkzeug の pbkdf2 でハッシュ化する（独自暗号は使わない）
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    def __repr__(self):
        return f"<User {self.username}>"
