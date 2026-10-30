"""認証まわりの振る舞いテスト.

正常系だけでなく「失敗したときに正しく失敗するか」を書く。
セキュリティ視点では、こちらが本番。
"""


def test_register_creates_user(client, app):
    from app.extensions import db
    from app.models import User

    response = client.post(
        "/auth/register",
        data={
            "username": "newbie01",
            "password": "password123",
            "password_confirm": "password123",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    user = db.session.scalar(db.select(User).where(User.username == "newbie01"))
    assert user is not None
    # パスワードは平文で保存されていない
    assert user.password_hash != "password123"


def test_register_rejects_short_password(client):
    response = client.post(
        "/auth/register",
        data={
            "username": "newbie02",
            "password": "short",
            "password_confirm": "short",
        },
        follow_redirects=True,
    )

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "8文字以上" in body


def test_register_rejects_bad_username(client):
    response = client.post(
        "/auth/register",
        data={
            "username": "あ い",
            "password": "password123",
            "password_confirm": "password123",
        },
        follow_redirects=True,
    )

    assert "ユーザー名は英数字とアンダースコア" in response.get_data(as_text=True)


def test_duplicate_username_is_rejected(client, make_user):
    make_user(username="taken01")

    response = client.post(
        "/auth/register",
        data={
            "username": "taken01",
            "password": "password123",
            "password_confirm": "password123",
        },
        follow_redirects=True,
    )

    assert "既に使用されています" in response.get_data(as_text=True)


def test_login_with_wrong_password_does_not_log_in(client, make_user):
    make_user(username="alice", password="password123")

    response = client.post(
        "/auth/login",
        data={"username": "alice", "password": "wrongpassword"},
        follow_redirects=True,
    )

    assert "正しくありません" in response.get_data(as_text=True)
    # まだ未ログインなので、保護ページはログインへ飛ばされる
    assert client.get("/auth/account").status_code == 302


def test_login_success_redirects(client, make_user):
    make_user(username="alice", password="password123")

    response = client.post(
        "/auth/login",
        data={"username": "alice", "password": "password123"},
    )

    assert response.status_code == 302
    assert client.get("/auth/account").status_code == 200


def test_login_rejects_external_next_url(client, make_user):
    """オープンリダイレクト対策: next が外部 URL なら / に落とす。"""

    make_user(username="alice", password="password123")

    response = client.post(
        "/auth/login?next=https://evil.example.com/",
        data={"username": "alice", "password": "password123"},
    )

    assert response.status_code == 302
    assert "evil.example.com" not in response.headers["Location"]
