"""ローカル起動確認用のスモークテスト（pytest ではない）。

python tools/smoke_check.py
で 登録 → 描画 → 保存 → 出品 → 入札 → 終了確定 までを通して確認する。
"""

from __future__ import annotations

import base64
import os
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

WORK_DIR = Path(tempfile.mkdtemp(prefix="hew-smoke-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(WORK_DIR / 'smoke.db').as_posix()}"
os.environ["SECRET_KEY"] = "smoke-secret-key"
os.environ["FLASK_ENV"] = "development"

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.services.image_service import create_solid_png  # noqa: E402

app = create_app()
app.config["UPLOAD_FOLDER"] = str(WORK_DIR / "uploads")
# スモークテストではフォームの CSRF 検証を省略する（ブラウザ経由では有効）
app.config["WTF_CSRF_ENABLED"] = False


def main() -> int:
    failures: list[str] = []

    def check(label: str, condition: bool) -> None:
        status = "OK " if condition else "NG "
        print(f"[{status}] {label}")
        if not condition:
            failures.append(label)

    with app.app_context():
        db.create_all()

    client = app.test_client()

    # 1) 登録（復旧コードが表示される）
    response = client.post(
        "/auth/register",
        data={
            "username": "smoke_user",
            "password": "password123",
            "password_confirm": "password123",
        },
        follow_redirects=True,
    )
    check("登録できる", response.status_code == 200)
    check("復旧コードが表示される", "復旧コード" in response.get_data(as_text=True))

    # 2) 描画開始
    response = client.post(
        "/artworks/draw/start", data={"duration_seconds": "300"}, follow_redirects=True
    )
    check("描画画面へ遷移する", "/canvas" in response.get_data(as_text=True))

    with app.app_context():
        from app.models.artwork import Artwork

        artwork = Artwork.query.first()
        artwork_id = artwork.id

    # 3) 正式保存（合成 PNG + レイヤー）
    raw = create_solid_png(512, 512, (30, 120, 200))
    data_url = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
    response = client.post(
        f"/artworks/{artwork_id}/save",
        json={
            "png": data_url,
            "layers": [
                {"name": "レイヤー1", "visible": True, "opacity": 1.0, "data": data_url}
            ],
            "finished": True,
        },
    )
    check("正式保存できる", response.status_code == 200 and response.get_json()["ok"])

    # 4) 出品
    response = client.post(
        f"/artworks/{artwork_id}/listing",
        data={
            "title": "スモークの作品",
            "description": "動作確認用",
            "start_price": "100",
            "duration_minutes": "10",
        },
        follow_redirects=True,
    )
    check("出品できる", response.status_code == 200)

    with app.app_context():
        from app.models.auction import Auction

        auction = Auction.query.first()
        auction_id = auction.id

    # 5) 入札（別ユーザー）
    client.post("/auth/logout")
    client.post(
        "/auth/register",
        data={
            "username": "smoke_bidder",
            "password": "password123",
            "password_confirm": "password123",
        },
        follow_redirects=True,
    )
    response = client.post(
        f"/auctions/{auction_id}/bid",
        data={"bid_amount": "300", "confirmed": "1"},
        follow_redirects=True,
    )
    check("入札できる", "入札を受け付けました" in response.get_data(as_text=True))

    # 6) 終了確定（CLI）
    with app.app_context():
        from app.models.auction import Auction
        from app.utils import utcnow

        auction = Auction.query.first()
        auction.end_time = utcnow() - timedelta(minutes=1)
        db.session.commit()

    runner = app.test_cli_runner()
    result = runner.invoke(args=["close-auctions"])
    check(
        "close-auctions が動く",
        result.exit_code == 0 and "オークションを確定" in result.output,
    )

    with app.app_context():
        from app.models.auction import Auction
        from app.models.user import User

        auction = Auction.query.first()
        seller = User.query.filter_by(username="smoke_user").first()
        check("落札者が記録される", auction.winner_id is not None)
        check("出品者へ落札額が加算される", seller.point_balance >= 300)

    # 7) 静的ファイルと公開画像
    response = client.get("/static/css/style.css")
    check("style.css を配信できる", response.status_code == 200)
    response = client.get(f"/artworks/{artwork_id}/image")
    check("公開画像を配信できる", response.status_code == 200)

    print()
    if failures:
        print(f"FAILED: {len(failures)} 件 → {failures}")
        return 1
    print("すべての項目 overcame")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
