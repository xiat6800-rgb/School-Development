# School-Development

HEW2026 チームプロジェクトの共有リポジトリ。複数の AI ツールで制作した実装を 1 つにまとめています。

## ディレクトリ構成

| パス | 内容 |
| --- | --- |
| `設計・要件/` | 要件定義書（日本語） |
| `HEW2026_v1.0_MiniMaxCode_high/` | MiniMax Code + MiniMax M3.1 Flash 実装（v1.0、Ver0.5 範囲） |
| `HEW2026_v1.0_MiniMaxCode_xhigh/` | 上記の xhigh 版（データモデル刷新、既定 DB は MySQL） |
| `docs/` | 並行開発の要求書・進行メモ |
| `系统组成.txt` | 構成メモ |

旧実装（`HEW2026_v1.0_MiMo-2.6-pro`／`HEW2026_v1.0_Qoder_中`／`HEW2026_v1.0_TraeWorkCN_高`）および `hew2026-workflow-workshop` は削除済みです。

## 開発ルール

- `.gitattributes` で改行コードを LF に統一済み（CRLF 混入による偽差分は出ません）
- ブランチは `网页`（HEW2026 本体）／`应用`／`系统` の 3 本。`main` は廃止した
- `网页` に実装一式を置き、`应用` と `系统` は今後の作業用に空けてある（README のみ）
- 3 本とも現在ブランチ保護は設定していない

## CI

CI 設定は `.github/workflows/ci.yml` に置きます。接続中の GitHub App に `workflows` 権限がないため `.github/workflows/` へ直接書き込めないため、現在は `.github/ci.yml` に置いています。`git mv .github/ci.yml .github/workflows/ci.yml` で確定してください。

`.github/workflows/ci.yml` は `网页` ブランチを対象に、matrix で残している 2 実装（`HEW2026_v1.0_MiniMaxCode_xhigh` と `HEW2026_v1.0_MiniMaxCode_high`）をそれぞれ検証します。

- **Lint + Test** — Ruff（構文・未定義名の検査、ブロッキング）＋ Pytest
- **Security checks** — Bandit（静的セキュリティ診断）＋ pip-audit（既知 CVE）

両実装とも `SELECT ... FOR UPDATE` の行ロックを使うため、CI は MySQL 8 サービスに接続して動かします。
テスト DB は実装ごとに専用（`hew_xhigh_test` / `hew_test`）。xhigh の `test_config.py` は
テスト DB 名が `hew_xhigh_test` であることを前提にしているため、名前を変えるとテストが落ちます。
`jobs.<id>.steps[*].working-directory` は `${{ env.X }}` を解決できないため、対象パスは matrix のリテラルで書いています。

## ローカルでのテスト

```powershell
cd HEW2026_v1.0_MiniMaxCode_xhigh
pip install -r requirements.txt
pip install pytest pytest-cov ruff
$env:SECRET_KEY = "local-dummy-secret"
pytest tests -q --cov=app
```

`pytest.ini` で `pythonpath = .` を固定しているため、ルート実行でも `python -m pytest` でも import が揃います。
