"""開発サーバー起動用のエントリーポイント。

本番では WSGI サーバー（Gunicorn 等）から
``app:create_app()`` を読み込む。
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)