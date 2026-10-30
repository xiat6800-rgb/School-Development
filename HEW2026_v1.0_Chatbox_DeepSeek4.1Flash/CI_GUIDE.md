# CI スターター（HEW2026 用）

Flask + pytest のプロジェクトに、GitHub Actions で
「Lint → テスト → セキュリティ検査 →（main のみ）デプロイ」を回すための最小セット。

## 置き場所

プロジェクト直下（`main.py` と同じ階層）にコピーする。

```
HEW2026_v1.0_xxx/
├── .github/
│   └── workflows/
│       └── ci.yml
├── tests/
│   ├── conftest.py
│   ├── test_smoke.py
│   ├── test_auth.py
│   └── test_clock.py
├── app/
├── requirements.txt
└── main.py
```

コピーは PowerShell で:

```powershell
$dst = 'C:\Users\12764\Desktop\基础开发\网页开发\HEW2026\HEW2026_v1.0_Chatbox_DeepSeek4.1Flash'
Copy-Item -Recurse -Force .\.github $dst
Copy-Item -Recurse -Force .\tests  $dst
```

## ローカルでまず緑にする

CI に push する前に、自分の PC で同じことをやる。これが CI の第一原則
（「ローカルで通らないものは CI でも通らない」）。

```powershell
cd 'C:\Users\12764\Desktop\基础开发\网页开发\HEW2026\HEW2026_v1.0_Chatbox_DeepSeek4.1Flash'
python -m pytest -q
python -m ruff check .
```

## 現在の状態（重要）

`pytest` を実行すると **17 件中 1 件が赤**になる。これはテストのバグではなく、
**アプリのバグをテストが見つけた** という正しい状態。

```
FAILED tests/test_auth.py::test_login_success_redirects
BuildError: Could not build url for endpoint 'points.charge'.
             Did you mean 'points.show_charge' instead?
```

原因: `app/templates/account/index.html` の 15 行目。

```html
<!-- 誤 -->
<a class="small-link" href="{{ url_for('points.charge') }}">チャージ</a>
<!-- 正 -->
<a class="small-link" href="{{ url_for('points.show_charge') }}">チャージ</a>
```

`/auth/account` を開くと 500 になる、という実害のあるバグ。
直せば 17 件すべて緑になる。**これが CI を入れる価値そのもの**。

## GitHub 側の初期設定（1 回だけ）

1. GitHub で空のリポジトリを作る（Private でよい）。
2. プロジェクト直下で:

```powershell
git init
git config core.quotepath false      # 日本語ファイル名を \346\227\245 にしない
git config core.autocrlf false       # 改行コード差分の大量発生を防ぐ
git add .
git commit -m "chore: add CI workflow and tests"
git branch -M main
git remote add origin https://github.com/<your-account>/<repo>.git
git push -u origin main
```

3. push した瞬間に Actions が走る。赤なら Files changed → ログを読む。
4. Settings → Branches → `main` を保護し、
   **Require status checks to pass** に `Lint + Test` を入れる
   → 赤いまま merge できなくなる（＝ CI が意味を持つ）。

## デプロイ（CD）を有効にする

1. Render / Railway などで Web Service を作り、Deploy Hook URL を取得。
2. GitHub の Settings → Secrets and variables → Actions →
   `DEPLOY_HOOK_URL` を登録。
3. `main` に merge すると deploy ジョブが動く。
   未設定なら「スキップします」で緑のまま終わる設計にしてある。

## 次にやると効くこと

- `--cov-fail-under=60` を付けてカバレッジの下限を決める
- 自作ランナー（自宅のラズベリーパイ）で `runs-on: self-hosted`
- Azure を使う授業に合わせるなら、同じ考え方を Azure Pipelines で書き直してみる
  （`azure-pipelines.yml`。工程名は違うが中身は同じ）
