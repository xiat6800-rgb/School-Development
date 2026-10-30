"""配線（ルーティング）が壊れていないことだけを見る最小テスト.

CI の最初の 1 本は「アプリが起動して 200 を返すか」で十分。
ここが赤なら、他のテストを読む前に環境か import が壊れている。
"""


def test_index_returns_200(client):
    response = client.get("/")
    assert response.status_code == 200


def test_login_page_returns_200(client):
    response = client.get("/auth/login")
    assert response.status_code == 200


def test_unknown_path_returns_404_page(client):
    response = client.get("/this-path-does-not-exist")
    assert response.status_code == 404
    assert "見つかりません" in response.get_data(as_text=True)


def test_protected_page_redirects_to_login(client):
    """/auth/account は login_required。未ログインならログイン画面へ。"""

    response = client.get("/auth/account")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]
