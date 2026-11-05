from app.extensions import db
from app.models import User, WalletTransaction
from tests.conftest import login, register


def test_register_shows_recovery_code_and_bonus(app, client):
    response = register(client, "alice")
    assert response.status_code == 200
    assert "復旧コード" in response.get_data(as_text=True)

    with app.app_context():
        user = User.query.filter_by(username="alice").first()
        assert user is not None
        assert user.recovery_code_hash is not None
        assert user.point_balance == 1000
        grants = user.wallet_transactions.all()
        assert any(t.transaction_type == WalletTransaction.TYPE_BONUS for t in grants)


def test_register_rejects_duplicate_username(app, client):
    register(client, "alice")
    response = register(client, "alice")
    assert "すでに使われています" in response.get_data(as_text=True)


def test_register_requires_event_open(app, client):
    from datetime import datetime, timedelta, timezone

    app.config["EVENT_END_AT"] = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
    response = register(client, "late")
    assert "イベントは終了" in response.get_data(as_text=True)
    with app.app_context():
        assert User.query.filter_by(username="late").first() is None


def test_login_logout(app, client):
    register(client, "alice")
    response = login(client, "alice")
    assert "ログアウト" in response.get_data(as_text=True)
    response = client.post("/logout", follow_redirects=True)
    assert "ログイン" in response.get_data(as_text=True)


def test_login_rejects_wrong_password(app, client):
    register(client, "alice")
    response = login(client, "alice", "wrong-password")
    assert "正しくありません" in response.get_data(as_text=True)


def test_password_reset_with_recovery_code(app, client):
    response = register(client, "alice")
    text = response.get_data(as_text=True)
    # 表示された復旧コード（XXXX-XXXX-XXXX-XXXX）を拾う
    import re

    match = re.search(r"[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}", text)
    assert match is not None
    code = match.group(0)

    response = client.post(
        "/reset-password",
        data={
            "username": "alice",
            "recovery_code": code,
            "password": "newpassword1",
            "password_confirm": "newpassword1",
        },
        follow_redirects=True,
    )
    assert "再設定しました" in response.get_data(as_text=True)

    with app.app_context():
        user = User.query.filter_by(username="alice").first()
        assert user.recovery_code_hash is None

    assert login(client, "alice", "newpassword1").status_code == 200
    # 使ったコードは再利用できない
    response = client.post(
        "/reset-password",
        data={
            "username": "alice",
            "recovery_code": code,
            "password": "anotherpass1",
            "password_confirm": "anotherpass1",
        },
        follow_redirects=True,
    )
    assert "正しくありません" in response.get_data(as_text=True)


def test_regenerate_recovery_code_invalidates_old(app, client):
    import re

    response = register(client, "alice")
    old_code = re.search(
        r"[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}",
        response.get_data(as_text=True),
    ).group(0)

    login(client, "alice")
    response = client.post(
        "/account/recovery-code",
        data={"password": "password123"},
        follow_redirects=True,
    )
    new_code = re.search(
        r"[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}",
        response.get_data(as_text=True),
    ).group(0)
    assert new_code != old_code

    response = client.post(
        "/reset-password",
        data={
            "username": "alice",
            "recovery_code": old_code,
            "password": "whatever123",
            "password_confirm": "whatever123",
        },
        follow_redirects=True,
    )
    assert "正しくありません" in response.get_data(as_text=True)


def test_update_display_name(app, client):
    register(client, "alice")
    login(client, "alice")
    response = client.post(
        "/account/display-name",
        data={"disp_name": "アリス"},
        follow_redirects=True,
    )
    assert "アリス" in response.get_data(as_text=True)
    with app.app_context():
        user = User.query.filter_by(username="alice").first()
        assert user.disp_name == "アリス"
