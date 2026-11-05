import os

import pytest

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import User
from app.services.tag_service import seed_initial_tags


@pytest.fixture()
def app(tmp_path):
    class TestConfig(TestingConfig):
        SQLALCHEMY_DATABASE_URI = "sqlite://"
        UPLOAD_FOLDER = os.path.join(str(tmp_path), "uploads")

    application = create_app(TestConfig)
    with application.app_context():
        db.create_all()
        seed_initial_tags()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def create_user(username, email, balance=0, password="password123"):
    user = User(username=username, email=email, disp_name=username, role="user")
    user.set_password(password)
    user.point_balance = balance
    db.session.add(user)
    db.session.flush()
    return user


def login(client, email, password="password123"):
    return client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


SMALL_PNG = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
