"""認証・権限のテスト（要件定義書 8章「認証・権限」）。"""
import re

from app.models.user import User

from conftest import create_saved_artwork, login, logout, register


def test_register_grants_signup_bonus_and_default_disp_name(client, app):
    response, code = register(client, "alice")
    assert response.status_code == 200
    assert code and re.fullmatch(r"[A-Z0-9]{16}", code)
    with app.app_context():
        user = User.query.filter_by(username="alice").first()
        assert user.point_balance == 1000
        assert user.disp_name == f"user{user.id}"
        assert user.recovery_code_hash  # ハッシュだけ保存


def test_register_rejects_duplicate_username(client):
    register(client, "bob")
    logout(client)
    response, code = register(client, "bob")
    assert code is None
    assert "既に使われています" in response.get_data(as_text=True)


def test_login_logout(client):
    register(client, "carol")
    logout(client)
    response = login(client, "carol", "wrongpass")
    assert "正しくありません" in response.get_data(as_text=True)
    response = login(client, "carol")
    assert "carol" not in response.request.path or response.request.path == "/"
    logout(client)
    response = client.get("/account", follow_redirects=True)
    assert "ログイン" in response.get_data(as_text=True)


def test_reset_password_uses_and_invalidates_code(client, app):
    _, code = register(client, "dave")
    logout(client)
    response = client.post(
        "/reset-password",
        data={"username": "dave", "recovery_code": code, "new_password": "newpass1"},
        follow_redirects=True,
    )
    assert "再設定しました" in response.get_data(as_text=True)
    # 使用済みコードは無効
    response = client.post(
        "/reset-password",
        data={"username": "dave", "recovery_code": code, "new_password": "another1"},
        follow_redirects=True,
    )
    assert "正しくありません" in response.get_data(as_text=True)
    login(client, "dave", "newpass1")


def test_regenerate_recovery_code_invalidates_old(client):
    _, old_code = register(client, "erin")
    response = client.post(
        "/account/recovery-code", data={"password": "pass1234"},
        follow_redirects=True,
    )
    match = re.search(r'class="code">([A-Z0-9]+)<', response.get_data(as_text=True))
    new_code = match.group(1)
    assert new_code != old_code
    logout(client)
    response = client.post(
        "/reset-password",
        data={"username": "erin", "recovery_code": old_code, "new_password": "x12345"},
        follow_redirects=True,
    )
    assert "正しくありません" in response.get_data(as_text=True)
    response = client.post(
        "/reset-password",
        data={"username": "erin", "recovery_code": new_code, "new_password": "x12345"},
        follow_redirects=True,
    )
    assert "再設定しました" in response.get_data(as_text=True)


def test_regenerate_requires_correct_password(client):
    register(client, "frank")
    response = client.post(
        "/account/recovery-code", data={"password": "badpass"},
        follow_redirects=True,
    )
    assert "パスワードが正しくありません" in response.get_data(as_text=True)


def test_draft_is_private(client):
    artwork_id = create_saved_artwork(client, "owner")
    logout(client)
    register(client, "other")
    assert client.get(f"/artworks/draft/{artwork_id}").status_code == 403
    assert client.get(f"/artworks/{artwork_id}/download/png").status_code == 403
    # 未保存・非公開の画像配信も他人には拒否
    assert client.get(f"/artworks/{artwork_id}/image").status_code == 403


def test_update_display_name(client, app):
    register(client, "gina")
    client.post("/account/display-name", data={"disp_name": "ジーナ"}, follow_redirects=True)
    with app.app_context():
        assert User.query.filter_by(username="gina").first().disp_name == "ジーナ"
