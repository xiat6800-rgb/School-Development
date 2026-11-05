"""認証・復旧コードのテスト（要件定義書 5.1 / 完成条件「認証・権限」）。"""

from __future__ import annotations

from app.extensions import db
from app.models.user import User


def test_register_creates_user_and_grants_signup_bonus(client):
    response = client.post(
        "/auth/register",
        data={
            "username": "newuser",
            "password": "password123",
            "password_confirm": "password123",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    user = User.query.filter_by(username="newuser").first()
    assert user is not None
    assert user.point_balance == 1000
    assert "復旧コード" in response.get_data(as_text=True)


def test_register_rejects_duplicated_username(client, make_user):
    make_user("taken")
    response = client.post(
        "/auth/register",
        data={
            "username": "taken",
            "password": "password123",
            "password_confirm": "password123",
        },
        follow_redirects=True,
    )
    assert "すでに使用されています" in response.get_data(as_text=True)
    assert User.query.filter_by(username="taken").count() == 1


def test_register_rejects_mismatched_password(client):
    response = client.post(
        "/auth/register",
        data={
            "username": "mismatch",
            "password": "password123",
            "password_confirm": "different123",
        },
        follow_redirects=True,
    )
    assert "一致しません" in response.get_data(as_text=True)
    assert User.query.filter_by(username="mismatch").first() is None


def test_login_and_logout(client, make_user, login):
    make_user("alice")
    response = login("alice")
    assert "ログインしました" in response.get_data(as_text=True)

    response = client.post("/auth/logout", follow_redirects=True)
    assert "ログアウトしました" in response.get_data(as_text=True)


def test_login_rejects_wrong_password(client, make_user, login):
    make_user("alice")
    response = login("alice", "wrongpassword")
    assert "正しくありません" in response.get_data(as_text=True)


def test_recover_password_with_recovery_code(client, make_user):
    user = make_user("alice")
    code = "TEST-CODE-1234"
    user.set_recovery_code(code)
    db.session.commit()

    response = client.post(
        "/auth/recover",
        data={
            "username": "alice",
            "recovery_code": code,
            "new_password": "newpassword1",
            "new_password_confirm": "newpassword1",
        },
        follow_redirects=True,
    )
    assert "パスワードを再設定しました" in response.get_data(as_text=True)

    db.session.expire_all()
    refreshed = User.query.filter_by(username="alice").first()
    assert refreshed.check_password("newpassword1")
    # 使用した復旧コードは無効化される
    assert refreshed.recovery_code_hash is None
    assert not refreshed.check_recovery_code(code)


def test_recover_rejects_wrong_code(client, make_user):
    user = make_user("alice")
    user.set_recovery_code("TEST-CODE-1234")
    db.session.commit()

    response = client.post(
        "/auth/recover",
        data={
            "username": "alice",
            "recovery_code": "WRONG-CODE-000",
            "new_password": "newpassword1",
            "new_password_confirm": "newpassword1",
        },
        follow_redirects=True,
    )
    assert "正しくありません" in response.get_data(as_text=True)
    db.session.expire_all()
    assert User.query.filter_by(username="alice").first().check_password("password123")


def test_regenerate_recovery_code_requires_password(client, make_user, login):
    user = make_user("alice")
    old_code = "OLD-CODE-0000"
    user.set_recovery_code(old_code)
    db.session.commit()
    login("alice")

    response = client.post(
        "/account/recovery-code",
        data={"password": "wrongpassword"},
        follow_redirects=True,
    )
    assert "現在のパスワードが正しくありません" in response.get_data(as_text=True)

    response = client.post(
        "/account/recovery-code",
        data={"password": "password123"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "復旧コード" in body
    db.session.expire_all()
    refreshed = User.query.filter_by(username="alice").first()
    assert not refreshed.check_recovery_code(old_code)
