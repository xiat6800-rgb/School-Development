"""LinguaFlow 基础回归测试。"""
import pytest

from app import create_app
from app.models import Course, Language, Lesson


@pytest.fixture()
def app(tmp_path):
    db_path = tmp_path / "test.db"
    app = create_app(
        {
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "test",
        }
    )
    with app.app_context():
        assert Language.query.count() == 3
        assert Course.query.count() == 9
        assert Lesson.query.count() == 36
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


def register(client, username="tester"):
    return client.post(
        "/auth/register",
        data={
            "username": username,
            "email": f"{username}@example.com",
            "password": "secret123",
            "confirm": "secret123",
        },
        follow_redirects=True,
    )


def test_public_pages(client, app):
    with app.app_context():
        course_id = Course.query.first().id
        post_id = 1
    for url in [
        "/",
        "/languages",
        f"/course/{course_id}",
        "/community",
        f"/community/{post_id}",
        "/auth/login",
        "/auth/register",
    ]:
        response = client.get(url)
        assert response.status_code == 200, url


def test_register_and_auth_pages(client):
    assert register(client).status_code == 200
    for url in ["/dashboard", "/progress", "/achievements", "/profile", "/lesson/1"]:
        assert client.get(url).status_code == 200, url
    assert client.get("/auth/logout", follow_redirects=True).status_code == 200


def test_complete_lesson_rewards_and_stats(client, app):
    register(client)
    with app.app_context():
        lesson_id = Lesson.query.filter_by(kind="vocab").first().id
    result = client.post(f"/api/lesson/{lesson_id}/complete", json={"score": 100})
    assert result.status_code == 200
    payload = result.get_json()
    assert payload["ok"] is True
    assert payload["score"] == 100
    assert payload["xp"] > 0
    assert payload["streak"] == 1
    assert any(a["code"] == "first_step" for a in payload["achievements"])

    stats = client.get("/api/stats").get_json()["stats"]
    assert stats["totals"]["lessons"] == 1
    assert stats["today"]["xp"] > 0


def test_locked_level_requires_previous(client, app):
    register(client)
    with app.app_context():
        locked = Course.query.filter_by(level=2).first()
        locked_lesson = locked.lessons[0].id
    response = client.get(f"/lesson/{locked_lesson}")
    assert response.status_code == 302


def test_community_post_like_comment(client):
    register(client, "social_user")
    created = client.post(
        "/api/posts",
        json={
            "title": "我的英语学习心得",
            "content": "每天坚持跟读十分钟，感觉口语进步明显。",
            "language_code": "en",
        },
    )
    assert created.status_code == 200
    post_id = created.get_json()["post_id"]

    like = client.post(f"/api/posts/{post_id}/like")
    assert like.get_json()["liked"] is True
    assert like.get_json()["count"] == 1

    comment = client.post(
        f"/api/posts/{post_id}/comments", json={"content": "一起加油！"}
    )
    assert comment.status_code == 200
    assert comment.get_json()["comment"]["count"] == 1
