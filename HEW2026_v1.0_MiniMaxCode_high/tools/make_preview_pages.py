"""スタイル確認用の静的プレビュー生成（開発用・一時ファイル）。

ログインが必要な画面（描画台・アカウント・出品設定）をテストクライアントで
描画し、``app/static/_preview_*.html`` へ書き出す。静的配信し���
Edge/Chrome の headless でスクリーンショットを撮るためだけに使う。
確認後はこのファイルと生成物を削除すること。
"""

from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402


def main() -> int:
    app = create_app()
    app.config["WTF_CSRF_ENABLED"] = False
    static_dir = BASE_DIR / "app" / "static"

    with app.app_context():
        from app.models.user import User
        from app.services.artwork_service import start_drawing_session

        seller = User.query.filter_by(username="sample1").first()
        artwork, _session = start_drawing_session(seller, 300)
        db.session.commit()
        canvas_id = artwork.id
        auction_id = db.session.execute(db.text("SELECT id FROM auctions LIMIT 1")).scalar()

    client = app.test_client()
    with client:
        client.post(
            "/auth/login",
            data={"username": "sample1", "password": "preview1234"},
            follow_redirects=True,
        )
        pages = {
            "_preview_canvas.html": f"/artworks/{canvas_id}/canvas",
            "_preview_account.html": "/account/?tab=drafts",
            "_preview_listing.html": f"/artworks/{canvas_id}/listing",
            "_preview_auction.html": f"/auctions/{auction_id}",
            "_preview_search.html": "/search/?tag_ids=1",
            "_preview_bonus.html": "/points/bonus",
        }
        for filename, path in pages.items():
            response = client.get(path)
            (static_dir / filename).write_text(
                response.get_data(as_text=True), encoding="utf-8"
            )
            print(f"wrote {filename} <- {path} ({response.status_code})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
