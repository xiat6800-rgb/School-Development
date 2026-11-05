# School-Development

HEW2026 チームプロジェクトの共有リポジトリ。複数の AI ツールで制作した実装を 1 つにまとめています。

## ディレクトリ構成

| パス | 内容 |
| --- | --- |
| `設計・要件/` | 要件定義書（日本語） |
| `HEW2026_v1.0_MiniMaxCode_high/` | MiniMax Code + MiniMax M3.1 Flash 実装（v1.0、Ver0.5 範囲） |
| `HEW2026_v1.0_MiniMaxCode_xhigh/` | 上記の xhigh 版（データモデル刷新、既定 DB は MySQL） |
| `HEW2026_v1.0_MiMo-2.6-pro/` | Xiaomi MiMo 2.6 Pro 実装（v1.0） |
| `HEW2026_v1.0_Qoder_中/` | Qoder（思考程度：中）実装（v1.0、Ver0.5 範囲） |
| `HEW2026_v1.0_TraeWorkCN_高/` | TraeWorkCN + DeepSeek 実装（v1.0） |
| `docs/` | 並行開発の要求書・進行メモ |
| `hew2026-workflow-workshop/` | GitHub Actions の学習用サンプル |
| `系统组成.txt` | 構成メモ |

## 開発ルール

- `.gitattributes` で改行コードを LF に統一済み（CRLF 混入による偽差分は出ません）
- ブランチは `网页`（HEW2026 本体）／`应用`／`系统` の 3 本。`main` は廃止した
- `网页` に実装一式を置き、`应用` と `系统` は今後の作業用に空けてある（README のみ）
- 3 本とも現在ブランチ保護は設定していない

## CI

`.github/workflows/ci.yml` は現状 `main`（廃止済み）と `HEW2026_v1.0_Chatbox_DeepSeek4.1Flash/`（削除済み）を参照したままで、新しい構成に合わせた更新が必要です。

- **Lint + Test** — Ruff（構文・未定義名の検査、ブロッキング）＋ Pytest
- **Security checks** — Bandit（静的セキュリティ診断）＋ pip-audit（既知 CVE）

現在 CI が読む実装は無い（旧パスのみを参照）ため、対象実装を決めて `ci.yml` を書き換える必要があります。
`jobs.<id>.defaults.run.working-directory` は `${{ env.X }}` を解決できないため、パスはリテラルで書いています。

## ローカルでのテスト

```powershell
cd HEW2026_v1.0_MiniMaxCode_xhigh
pip install -r requirements.txt
pip install pytest pytest-cov ruff
$env:SECRET_KEY = "local-dummy-secret"
pytest tests -q --cov=app
```

`pytest.ini` で `pythonpath = .` を固定しているため、ルート実行でも `python -m pytest` でも import が揃います。
