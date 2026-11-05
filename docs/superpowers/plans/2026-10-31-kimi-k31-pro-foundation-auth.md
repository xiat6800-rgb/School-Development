# Kimi K3.1 Pro Foundation and Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first independently testable increment of `HEW2026_v1.0_Chatbox_KimiK3.1Pro/`: a runnable Flask application with the approved visual foundation, username authentication, recovery codes, account settings, and the 1,000 pt registration bonus.

**Architecture:** Use an Application Factory, Blueprints, SQLAlchemy models, and service functions. Routes handle HTTP and forms; services own credential and wallet rules. Later plans add drawing, auctions, and discovery on top of these interfaces without changing MiniMax or restoring the deleted historical Kimi code.

**Tech Stack:** Python 3.13, Flask, Flask-SQLAlchemy, Flask-Migrate, Flask-Login, Flask-WTF, SQLite for tests and development, Jinja2, native CSS/JavaScript, Pytest.

## Global Constraints

- Project root: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/` under the repository root.
- UI copy is Japanese; visual direction is warm white, near-black typography, blue-violet accents, rounded cards, and clear focus states.
- Never modify `HEW2026_v1.0_MiniMaxCode_MiniMaxM3.1Flash/`.
- Do not copy MiniMax source files or restore `HEAD:HEW2026_v1.0_Chatbox_KimiK3.1Pro`.
- Username authentication only; no email fields.
- Passwords and recovery codes are hashed at rest; plaintext recovery codes are shown once.
- Registration grants exactly 1,000 pt once through an idempotent wallet reference.
- All POST routes have CSRF protection; tests disable CSRF only through test configuration.
- Use UTC for database timestamps and Asia/Tokyo for displayed timestamps.
- Do not commit `.env`, secrets, `instance/`, or uploaded files.
- Do not run `git commit`, `git push`, `git reset`, or `git rebase` unless the user explicitly requests it.
- Run commands from the new project root. Use `python -m pytest` rather than a globally installed pytest entry point.
- This is Phase 1 of the approved rebuild. Phase 2 covers drawing and listing, Phase 3 covers bidding and settlement, and Phase 4 covers search, favorites, notifications, account history, final responsive polish, and end-to-end verification.

---

## File Structure

- `main.py`: development entry point and `--host` / `--port` parsing.
- `package.json`: dependency-free `npm run dev` forwarding to `main.py`.
- `app/__init__.py`: application factory, extension and Blueprint registration, error handlers.
- `app/config.py`: environment configuration and production secret validation.
- `app/extensions.py`: shared Flask extension instances.
- `app/models/user.py`: user credentials, display name, and balance.
- `app/models/wallet.py`: idempotent point ledger entries.
- `app/services/auth_service.py`: registration, authentication, recovery, and profile operations.
- `app/services/point_service.py`: transactional point grants and duplicate-reference protection.
- `app/services/errors.py`: shared business exceptions.
- `app/auth/forms.py`: authentication and recovery forms.
- `app/auth/routes.py`: register, login, logout, and recovery HTTP endpoints.
- `app/account/forms.py`: display-name and recovery-code forms.
- `app/account/routes.py`: account view, display-name update, and recovery-code reissue.
- `app/templates/`: Japanese pages using the approved visual foundation.
- `app/static/css/app.css`: shared responsive design system.
- `tests/`: isolated SQLite tests; never uses the development database.

### Task 1: Runnable Application Foundation

**Files:**
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/main.py`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/package.json`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/requirements.txt`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/pytest.ini`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/.gitignore`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/.env.example`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/__init__.py`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/config.py`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/extensions.py`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/main/__init__.py`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/main/routes.py`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/templates/base.html`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/templates/main/index.html`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/templates/errors/404.html`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/static/css/app.css`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/tests/conftest.py`
- Test: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/tests/test_foundation.py`

**Interfaces:**
- Consumes: none.
- Produces: `create_app(test_config: dict | None = None) -> Flask`; `db`, `migrate`, `login_manager`, and `csrf` extension objects; `GET /` returning the Japanese home page.

- [ ] **Step 1: Write the failing application-factory test**

Create `tests/conftest.py`:

```python
import pytest

from app import create_app
from app.extensions import db


@pytest.fixture()
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
        "WTF_CSRF_ENABLED": False,
    })
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()
```

Create `tests/test_foundation.py`:

```python
def test_home_is_runnable_and_japanese(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "HEW".encode() in response.data
    assert "一枚の絵に、次の物語を。".encode() in response.data


def test_unknown_page_uses_custom_404(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert "ページが見つかりません".encode() in response.data
```

- [ ] **Step 2: Run the tests and verify the expected import failure**

Run:

```bash
python -m pytest tests/test_foundation.py -q
```

Expected: FAIL during collection because `app` does not exist.

- [ ] **Step 3: Create the minimal runnable application**

Create `requirements.txt`:

```text
Flask==3.1.2
Flask-SQLAlchemy==3.1.1
Flask-Migrate==4.1.0
Flask-Login==0.6.3
Flask-WTF==1.2.2
python-dotenv==1.1.1
PyMySQL==1.1.2
pytest==8.4.2
```

Create `pytest.ini`:

```ini
[pytest]
pythonpath = .
testpaths = tests
```

Create `.gitignore`:

```gitignore
.env
.venv/
__pycache__/
.pytest_cache/
instance/
*.pyc
```

Create `.env.example`:

```text
SECRET_KEY=replace-with-a-long-random-value
DATABASE_URL=sqlite:///hew_dev.db
FLASK_ENV=development
```

Create `app/config.py`:

```python
import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "development-only-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///hew_dev.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True


def validate_config(app):
    if os.getenv("FLASK_ENV") == "production" and not os.getenv("SECRET_KEY"):
        raise RuntimeError("本番環境では SECRET_KEY が必要です")
```

Create `app/extensions.py`:

```python
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect


db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
```

Create `app/__init__.py`:

```python
from flask import Flask, render_template
from dotenv import load_dotenv

from .config import Config, validate_config
from .extensions import csrf, db, login_manager, migrate


def create_app(test_config=None):
    load_dotenv()
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    validate_config(app)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "auth.login"

    from .main import bp as main_bp
    app.register_blueprint(main_bp)

    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html"), 404

    return app
```

Create `app/main/__init__.py` and `app/main/routes.py`:

```python
# app/main/__init__.py
from flask import Blueprint

bp = Blueprint("main", __name__)
from . import routes
```

```python
# app/main/routes.py
from flask import render_template
from . import bp


@bp.get("/")
def index():
    return render_template("main/index.html")
```

Create `app/templates/base.html`:

```html
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}HEW{% endblock %}</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='css/app.css') }}">
</head>
<body>
  <header class="site-header"><a class="brand" href="{{ url_for('main.index') }}">HEW<span>.</span></a></header>
  <main class="page-shell">{% block content %}{% endblock %}</main>
</body>
</html>
```

Create `app/templates/main/index.html`:

```html
{% extends "base.html" %}
{% block content %}
<section class="hero">
  <p class="eyebrow">DRAW. LIST. BID.</p>
  <h1>一枚の絵に、<br>次の物語を。</h1>
  <p>制限時間で描いて、ポイントで競るオンライン・アートオークション。</p>
</section>
{% endblock %}
```

Create `app/templates/errors/404.html`:

```html
{% extends "base.html" %}
{% block content %}<h1>ページが見つかりません</h1><p>URLをご確認ください。</p>{% endblock %}
```

Create `app/static/css/app.css` with the Phase 1 design tokens and responsive shell:

```css
:root{--bg:#f5f6f8;--surface:#fff;--ink:#15171a;--muted:#737986;--accent:#5267ff;--line:#dfe3ea;--radius:18px}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,"Yu Gothic",system-ui,sans-serif;line-height:1.6}a{color:inherit}.site-header{max-width:1180px;margin:auto;padding:24px;display:flex;align-items:center;justify-content:space-between}.brand{font-size:24px;font-weight:800;text-decoration:none}.brand span,.eyebrow{color:var(--accent)}.page-shell{max-width:1180px;margin:auto;padding:32px 24px}.hero{padding:8vh 0}.eyebrow{font-size:12px;font-weight:800;letter-spacing:.16em}.hero h1{font-size:clamp(42px,7vw,82px);line-height:1.08;letter-spacing:-.05em;margin:16px 0}.button{display:inline-block;border:0;border-radius:999px;background:var(--ink);color:#fff;padding:12px 22px;font-weight:700;cursor:pointer}.button:focus-visible,a:focus-visible,input:focus-visible{outline:3px solid var(--accent);outline-offset:3px}.form-card{max-width:480px;margin:40px auto;background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:32px}.field{margin-bottom:18px}.field label{display:block;font-weight:700}.field input{width:100%;padding:12px;border:1px solid var(--line);border-radius:10px;font:inherit}.error{color:#b42318}.flash{padding:12px 16px;border-radius:10px;background:#eef0ff;margin-bottom:20px}@media(max-width:600px){.page-shell{padding:20px 16px}.form-card{padding:24px}}
```

Create `main.py` and `package.json`:

```python
import argparse
from app import create_app

app = create_app()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    app.run(host=args.host, port=args.port, debug=app.config.get("ENV") == "development")
```

```json
{"name":"hew2026-kimi-k31-pro","private":true,"scripts":{"dev":"python main.py"}}
```

- [ ] **Step 4: Run the foundation tests**

Run:

```bash
python -m pytest tests/test_foundation.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Verify preview argument forwarding without leaving a server running**

Run:

```bash
python main.py --help
```

Expected: usage includes both `--host` and `--port`.

Run `npm run dev -- --host 127.0.0.1 --port 7100`, confirm one `GET /` returns 200, then stop that same process before continuing. Do not start an independent background server.

### Task 2: User Model and Idempotent Registration Bonus

**Files:**
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/models/__init__.py`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/models/user.py`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/models/wallet.py`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/services/__init__.py`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/services/errors.py`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/services/point_service.py`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/services/auth_service.py`
- Modify: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/__init__.py`
- Test: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/tests/test_auth_service.py`

**Interfaces:**
- Consumes: `db` from Task 1.
- Produces: `User(id, username, password_hash, recovery_code_hash, display_name, points)`; `WalletTransaction(user_id, amount, kind, reference_key)`; `register_user(username: str, password: str) -> tuple[User, str]`; `grant_points(user: User, amount: int, kind: str, reference_key: str) -> WalletTransaction`; `BusinessError(message: str)`.

- [ ] **Step 1: Write failing service tests**

Create `tests/test_auth_service.py`:

```python
import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.user import User
from app.models.wallet import WalletTransaction
from app.services.auth_service import authenticate, register_user
from app.services.errors import BusinessError


def test_registration_hashes_secrets_and_grants_1000_points(app):
    with app.app_context():
        user, recovery = register_user("artist01", "password123")
        assert user.id is not None
        assert user.display_name == f"user{user.id}"
        assert user.points == 1000
        assert user.password_hash != "password123"
        assert user.recovery_code_hash != recovery
        assert user.check_password("password123")
        assert user.check_recovery_code(recovery)
        entry = WalletTransaction.query.filter_by(user_id=user.id).one()
        assert (entry.amount, entry.kind) == (1000, "register_bonus")
        assert authenticate("artist01", "password123").id == user.id
        assert authenticate("artist01", "wrong-password") is None


def test_duplicate_username_is_rejected(app):
    with app.app_context():
        register_user("artist01", "password123")
        with pytest.raises(BusinessError, match="ユーザー名"):
            register_user("artist01", "password123456")
        db.session.rollback()
        assert User.query.count() == 1
        assert WalletTransaction.query.count() == 1
```

- [ ] **Step 2: Verify the tests fail on the missing model**

Run:

```bash
python -m pytest tests/test_auth_service.py -q
```

Expected: FAIL during collection with `ModuleNotFoundError: app.models`.

- [ ] **Step 3: Implement models and transactional registration**

Create `app/services/errors.py`:

```python
class BusinessError(ValueError):
    """Safe, user-facing business rule violation."""
```

Create `app/models/user.py`:

```python
from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    recovery_code_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(80), nullable=False)
    points = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def set_recovery_code(self, code):
        self.recovery_code_hash = generate_password_hash(code)

    def check_recovery_code(self, code):
        return check_password_hash(self.recovery_code_hash, code)
```

Create `app/models/wallet.py`:

```python
from datetime import datetime, timezone
from app.extensions import db


class WalletTransaction(db.Model):
    __tablename__ = "wallet_transactions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)
    kind = db.Column(db.String(40), nullable=False)
    reference_key = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
```

Create `app/models/__init__.py`:

```python
from .user import User
from .wallet import WalletTransaction

__all__ = ["User", "WalletTransaction"]
```

Create `app/services/point_service.py`:

```python
from app.extensions import db
from app.models.wallet import WalletTransaction


def grant_points(user, amount, kind, reference_key):
    if amount <= 0:
        raise ValueError("amount must be positive")
    existing = WalletTransaction.query.filter_by(reference_key=reference_key).first()
    if existing:
        return existing
    entry = WalletTransaction(user_id=user.id, amount=amount, kind=kind, reference_key=reference_key)
    user.points += amount
    db.session.add(entry)
    db.session.flush()
    return entry
```

Create `app/services/auth_service.py`:

```python
import secrets
from app.extensions import db
from app.models.user import User
from app.services.errors import BusinessError
from app.services.point_service import grant_points


def register_user(username, password):
    if User.query.filter_by(username=username).first():
        raise BusinessError("このユーザー名は既に使われています")
    user = User(username=username, display_name="temporary", points=0)
    user.set_password(password)
    recovery_code = secrets.token_urlsafe(12)
    user.set_recovery_code(recovery_code)
    db.session.add(user)
    db.session.flush()
    user.display_name = f"user{user.id}"
    grant_points(user, 1000, "register_bonus", f"register:{user.id}")
    db.session.commit()
    return user, recovery_code


def authenticate(username, password):
    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        return user
    return None
```

In `app/__init__.py`, import models after extension initialization and add the user loader:

```python
from . import models


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(models.User, int(user_id))
```

- [ ] **Step 4: Run service and foundation tests**

Run:

```bash
python -m pytest tests/test_auth_service.py tests/test_foundation.py -q
```

Expected: `4 passed`.

### Task 3: Registration, Login, Logout, and One-Time Recovery Display

**Files:**
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/auth/__init__.py`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/auth/forms.py`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/auth/routes.py`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/templates/auth/register.html`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/templates/auth/login.html`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/templates/auth/recovery_code.html`
- Modify: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/__init__.py`
- Modify: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/templates/base.html`
- Test: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/tests/test_auth_routes.py`

**Interfaces:**
- Consumes: `register_user()` and `authenticate()` from Task 2.
- Produces: `/auth/register`, `/auth/login`, `/auth/logout`, `/auth/recovery-code`; authenticated user available as `current_user`.

- [ ] **Step 1: Write failing route tests**

Create `tests/test_auth_routes.py`:

```python
import re
from app.models.user import User


def register(client, username="artist01"):
    return client.post("/auth/register", data={
        "username": username,
        "password": "password123",
        "password_confirm": "password123",
    }, follow_redirects=True)


def test_register_displays_recovery_once_and_logs_in(client, app):
    response = register(client)
    assert response.status_code == 200
    assert "復旧コード" in response.get_data(as_text=True)
    with app.app_context():
        assert User.query.filter_by(username="artist01").count() == 1
    second = client.get("/auth/recovery-code", follow_redirects=True)
    assert "復旧コードは一度だけ表示されます" in second.get_data(as_text=True)


def test_login_logout_and_invalid_password(client):
    register(client)
    client.post("/auth/logout")
    bad = client.post("/auth/login", data={"username": "artist01", "password": "bad-password"})
    assert "ユーザー名またはパスワード" in bad.get_data(as_text=True)
    good = client.post("/auth/login", data={"username": "artist01", "password": "password123"}, follow_redirects=True)
    assert "ログインしました" in good.get_data(as_text=True)
    out = client.post("/auth/logout", follow_redirects=True)
    assert "ログアウトしました" in out.get_data(as_text=True)


def test_duplicate_username_returns_form_error(client):
    register(client)
    client.post("/auth/logout")
    response = register(client)
    assert "このユーザー名は既に使われています" in response.get_data(as_text=True)
```

- [ ] **Step 2: Verify route tests fail with 404**

Run:

```bash
python -m pytest tests/test_auth_routes.py -q
```

Expected: FAIL; registration assertions receive the custom 404 page.

- [ ] **Step 3: Implement forms, routes, and exact Japanese templates**

Create `app/auth/forms.py`:

```python
from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField
from wtforms.validators import EqualTo, Length, Regexp


class RegisterForm(FlaskForm):
    username = StringField("ユーザー名", validators=[Length(min=3, max=50), Regexp(r"^[A-Za-z0-9_]+$", message="英数字と _ のみ使えます")])
    password = PasswordField("パスワード", validators=[Length(min=8, max=128)])
    password_confirm = PasswordField("パスワード（確認）", validators=[EqualTo("password", message="パスワードが一致しません")])


class LoginForm(FlaskForm):
    username = StringField("ユーザー名", validators=[Length(min=3, max=50)])
    password = PasswordField("パスワード", validators=[Length(min=1, max=128)])
```

Create `app/auth/__init__.py` and `app/auth/routes.py`:

```python
# app/auth/__init__.py
from flask import Blueprint
bp = Blueprint("auth", __name__, url_prefix="/auth")
from . import routes
```

```python
# app/auth/routes.py
from flask import flash, redirect, render_template, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from app.services.auth_service import authenticate, register_user
from app.services.errors import BusinessError
from . import bp
from .forms import LoginForm, RegisterForm


@bp.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        try:
            user, recovery = register_user(form.username.data, form.password.data)
        except BusinessError as exc:
            form.username.errors.append(str(exc))
        else:
            login_user(user)
            session["new_recovery_code"] = recovery
            return redirect(url_for("auth.recovery_code"))
    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = authenticate(form.username.data, form.password.data)
        if user:
            login_user(user)
            flash("ログインしました")
            return redirect(url_for("main.index"))
        form.password.errors.append("ユーザー名またはパスワードが正しくありません")
    return render_template("auth/login.html", form=form)


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    flash("ログアウトしました")
    return redirect(url_for("main.index"))


@bp.get("/recovery-code")
@login_required
def recovery_code():
    code = session.pop("new_recovery_code", None)
    if not code:
        flash("復旧コードは一度だけ表示されます")
        return redirect(url_for("main.index"))
    return render_template("auth/recovery_code.html", code=code)
```

Use this shared form markup exactly in `register.html` and `login.html`, changing only the title, fields, action, and submit label:

```html
{% extends "base.html" %}
{% block content %}
<div class="form-card">
  <h1>{{ title }}</h1>
  <form method="post" novalidate>
    {{ form.hidden_tag() }}
    {% for field in form if field.type != 'CSRFTokenField' %}
      <div class="field">{{ field.label }}{{ field() }}{% for error in field.errors %}<p class="error">{{ error }}</p>{% endfor %}</div>
    {% endfor %}
    <button class="button" type="submit">{{ submit_label }}</button>
  </form>
</div>
{% endblock %}
```

Render `register.html` with `title="新規登録"` and `submit_label="登録する"`; render `login.html` with `title="ログイン"` and `submit_label="ログイン"`. Add these values explicitly to both `render_template` calls rather than relying on undefined template variables.

Create `recovery_code.html`:

```html
{% extends "base.html" %}
{% block content %}<div class="form-card"><h1>復旧コード</h1><p>このコードは一度だけ表示されます。安全な場所に保存してください。</p><p><strong>{{ code }}</strong></p><a class="button" href="{{ url_for('main.index') }}">保存しました</a></div>{% endblock %}
```

Register `auth.bp` in `create_app`. In `base.html`, render flashed messages and show login/register links to guests, and the account/logout controls to authenticated users. Logout must remain a POST form containing `csrf_token()`.

- [ ] **Step 4: Run all current tests**

Run:

```bash
python -m pytest -q
```

Expected: `7 passed`.

### Task 4: Password Recovery and Account Settings

**Files:**
- Modify: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/services/auth_service.py`
- Modify: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/auth/forms.py`
- Modify: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/auth/routes.py`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/templates/auth/recover.html`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/account/__init__.py`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/account/forms.py`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/account/routes.py`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/templates/account/index.html`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/templates/account/recovery_code.html`
- Modify: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/__init__.py`
- Test: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/tests/test_recovery_account.py`

**Interfaces:**
- Consumes: `User`, `current_user`, and authentication Blueprint from Tasks 2–3.
- Produces: `reset_password(username: str, recovery_code: str, new_password: str) -> User`; `update_display_name(user: User, display_name: str) -> User`; `reissue_recovery_code(user: User, password: str) -> str`; `/auth/recover`, `/account/`, `/account/display-name`, `/account/recovery-code`.

- [ ] **Step 1: Write failing recovery and account tests**

Create `tests/test_recovery_account.py`:

```python
import re
from app.services.auth_service import authenticate
from tests.test_auth_routes import register


def extract_code(response):
    text = response.get_data(as_text=True)
    match = re.search(r"<strong>([^<]+)</strong>", text)
    assert match
    return match.group(1)


def test_recovery_code_resets_password_and_is_single_use(client):
    code = extract_code(register(client))
    client.post("/auth/logout")
    response = client.post("/auth/recover", data={"username": "artist01", "recovery_code": code, "password": "newpassword123", "password_confirm": "newpassword123"}, follow_redirects=True)
    assert "パスワードを再設定しました" in response.get_data(as_text=True)
    assert authenticate("artist01", "newpassword123")
    reused = client.post("/auth/recover", data={"username": "artist01", "recovery_code": code, "password": "anotherpass123", "password_confirm": "anotherpass123"})
    assert "復旧コード" in reused.get_data(as_text=True)


def test_account_updates_display_name_and_reissues_code(client):
    response = register(client)
    old_code = extract_code(response)
    changed = client.post("/account/display-name", data={"display_name": "月白アーティスト"}, follow_redirects=True)
    assert "月白アーティスト" in changed.get_data(as_text=True)
    reissued = client.post("/account/recovery-code", data={"password": "password123"})
    new_code = extract_code(reissued)
    assert new_code != old_code
    client.post("/auth/logout")
    assert authenticate("artist01", "password123")
```

- [ ] **Step 2: Verify the new routes fail**

Run:

```bash
python -m pytest tests/test_recovery_account.py -q
```

Expected: FAIL because `/auth/recover` and `/account/*` return 404.

- [ ] **Step 3: Implement single-use recovery and account operations**

Append to `app/services/auth_service.py`:

```python
def reset_password(username, recovery_code, new_password):
    user = User.query.filter_by(username=username).first()
    if not user or not user.check_recovery_code(recovery_code):
        raise BusinessError("ユーザー名または復旧コードが正しくありません")
    user.set_password(new_password)
    replacement = secrets.token_urlsafe(12)
    user.set_recovery_code(replacement)
    db.session.commit()
    return user


def update_display_name(user, display_name):
    user.display_name = display_name
    db.session.commit()
    return user


def reissue_recovery_code(user, password):
    if not user.check_password(password):
        raise BusinessError("パスワードが正しくありません")
    code = secrets.token_urlsafe(12)
    user.set_recovery_code(code)
    db.session.commit()
    return code
```

Add `RecoverForm` with `username`, `recovery_code`, `password`, and `password_confirm` fields, using the same length and confirmation validators as registration. Add `/auth/recover` as GET/POST: call `reset_password`, flash `パスワードを再設定しました`, redirect to login on success, and attach `BusinessError` to `recovery_code.errors` on failure.

Create `app/account/forms.py`:

```python
from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField
from wtforms.validators import Length


class DisplayNameForm(FlaskForm):
    display_name = StringField("表示名", validators=[Length(min=1, max=80)])


class ReissueRecoveryForm(FlaskForm):
    password = PasswordField("現在のパスワード", validators=[Length(min=1, max=128)])
```

Create an `account` Blueprint with `/account` prefix. Protect all routes with `login_required`. `GET /` renders `DisplayNameForm(obj=current_user)` and an empty `ReissueRecoveryForm`. `POST /display-name` calls `update_display_name`, flashes `表示名を更新しました`, and redirects to `/account/`. `POST /recovery-code` calls `reissue_recovery_code`; on success render `account/recovery_code.html` immediately with the new code, and on failure return the account page with the form error and status 400.

The account template must display `current_user.display_name`, `current_user.points`, both POST forms with `hidden_tag()`, and all field errors. The recovery-code template must use `<strong>{{ code }}</strong>` and state that the previous code is invalid and the new code is shown once.

Register `account.bp` in `create_app` and link `/account/` in the authenticated navigation.

- [ ] **Step 4: Run all Phase 1 tests**

Run:

```bash
python -m pytest -q
```

Expected: `9 passed`.

### Task 5: Error States, Responsive Navigation, Documentation, and Phase Gate

**Files:**
- Modify: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/__init__.py`
- Modify: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/templates/base.html`
- Modify: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/static/css/app.css`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/templates/errors/403.html`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/templates/errors/500.html`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/README.md`
- Test: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/tests/test_security_ui.py`

**Interfaces:**
- Consumes: all Phase 1 routes and templates.
- Produces: consistent 403/404/500 responses, responsive authenticated/guest navigation, reproducible setup and test instructions.

- [ ] **Step 1: Write failing security and UI tests**

Create `tests/test_security_ui.py`:

```python
def test_guest_account_access_redirects_to_login(client):
    response = client.get("/account/")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_error_page_and_mobile_viewport(client):
    response = client.get("/missing")
    html = response.get_data(as_text=True)
    assert response.status_code == 404
    assert 'name="viewport"' in html
    assert "ページが見つかりません" in html


def test_csrf_is_enabled_outside_testing(app):
    assert app.config["WTF_CSRF_ENABLED"] is False
    from app import create_app
    normal = create_app({"SECRET_KEY": "normal-secret", "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    assert normal.config["WTF_CSRF_ENABLED"] is True
```

- [ ] **Step 2: Run the security tests**

Run:

```bash
python -m pytest tests/test_security_ui.py -q
```

Expected: PASS for redirect, viewport, and CSRF configuration. If any assertion fails, correct the existing factory or template before continuing; do not weaken the assertions.

- [ ] **Step 3: Finish error handling and responsive shell**

Add 403 and 500 handlers to `create_app` using dedicated Japanese templates. The 403 page says `このページを表示する権限がありません`; the 500 page says `サーバーエラーが発生しました`. Neither page includes exception text or a stack trace. In testing, propagate unexpected exceptions rather than asserting a false successful 500 response.

Update `base.html` with a semantic `<nav aria-label="メインナビゲーション">`, real links for home/login/register/account, and a POST logout button. Add mobile CSS at `max-width: 600px` so navigation wraps, form controls remain at least 44 px high, and `.page-shell` has no fixed width. Preserve visible `:focus-visible` outlines.

Create `README.md` with these exact verified commands and explain that Phase 1 currently contains authentication and account functions:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -m flask --app main.py init-db
python main.py
```

Also document `npm run dev -- --host 127.0.0.1 --port 7100`, `python -m pytest -q`, SQLite development usage, MySQL `DATABASE_URL` format, the prohibition on committing `.env`, and the fact that drawing and auctions belong to later phases.

Add an `init-db` CLI command in `app/__init__.py`:

```python
@app.cli.command("init-db")
def init_db_command():
    """Create development database tables."""
    db.create_all()
    print("Database initialized")
```

- [ ] **Step 4: Run the complete Phase 1 verification**

Run:

```bash
python -m pytest -q
```

Expected: `12 passed`.

Run:

```bash
python main.py --help
```

Expected: exit code 0 and help for `--host` and `--port`.

- [ ] **Step 5: Perform the Phase 1 browser gate**

Start with `npm run dev -- --host 127.0.0.1 --port 7100`. Verify register, one-time recovery display, logout, login, password recovery, display-name update, recovery-code reissue, 404 page, and mobile-width navigation. Stop the development server before reporting completion. Record actual results; do not claim drawing or auction functionality in this phase.
