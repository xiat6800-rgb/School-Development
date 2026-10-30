# School-Development

HEW2026 チームプロジェクトの共有リポジトリ。複数の AI ツールで制作した実装を 1 つにまとめています。

## ディレクトリ構成

| パス | 内容 |
| --- | --- |
| `設計・要件/` | 要件定義書（日本語） |
| `HEW2026_v0.5_Chatbox_DeepSeek4.1Flash/` | Chatbox + DeepSeek 4.1 Flash 実装（v0.5） |
| `HEW2026_v1.0_Chatbox_DeepSeek4.1Flash/` | Chatbox + DeepSeek 4.1 Flash 実装（v1.0、CI 対象） |
| `HEW2026_v1.0_Chatbox_KimiK3.1Pro/` | Chatbox + Kimi K3.1 Pro 実装（v1.0） |
| `HEW2026_v1.0_TraeWorkCN_Deepseek/` | TraeWork CN + DeepSeek 実装（v1.0） |
| `hew2026-workflow-workshop/` | GitHub Actions の学習用サンプル |
| `系统组成.txt` / `执行错误/` | 構成メモとエラーメモ |

## 開発ルール

- `.gitattributes` で改行コードを LF に統一済み（CRLF 混入による偽差分は出ません）
- `main` は保護ブランチ。`enforce_admins=false` のため、owner は直接 push 可能
- ただし force push とブランチ削除は禁止

## CI

`.github/workflows/ci.yml` が `main` への push と PR で走ります。

- **Lint + Test** — Ruff（構文・未定義名の検査、ブロッキング）＋ Pytest
- **Security checks** — Bandit（静的セキュリティ診断）＋ pip-audit（既知 CVE）

CI が読むのは `HEW2026_v1.0_Chatbox_DeepSeek4.1Flash/` のみです。
`jobs.<id>.defaults.run.working-directory` は `${{ env.X }}` を解決できないため、パスはリテラルで書いています。

## ローカルでのテスト

```powershell
cd HEW2026_v1.0_Chatbox_DeepSeek4.1Flash
pip install -r requirements.txt
pip install pytest pytest-cov ruff
$env:SECRET_KEY = "local-dummy-secret"
pytest tests -q --cov=app
```

`pytest.ini` で `pythonpath = .` を固定しているため、ルート実行でも `python -m pytest` でも import が揃います。
