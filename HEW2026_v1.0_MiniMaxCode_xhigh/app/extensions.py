"""Flask 拡張機能のインスタンス。

Blueprint から直接 import すると循環参照になるため、
拡張機能のインスタンスはここに一元化する。
"""

from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "この画面はログインが必要です。"
csrf = CSRFProtect()
