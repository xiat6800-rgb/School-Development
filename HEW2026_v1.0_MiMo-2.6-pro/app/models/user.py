from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False, index=True)
    disp_name = db.Column(db.String(50), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    recovery_code_hash = db.Column(db.String(255), nullable=True)
    role = db.Column(db.String(10), nullable=False, default="user")
    point_balance = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now(),
        nullable=False,
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def set_recovery_code(self, code):
        self.recovery_code_hash = generate_password_hash(code)

    def check_recovery_code(self, code):
        if not self.recovery_code_hash:
            return False
        return check_password_hash(self.recovery_code_hash, code)

    def clear_recovery_code(self):
        self.recovery_code_hash = None

    @property
    def is_admin(self):
        return self.role == "admin"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
