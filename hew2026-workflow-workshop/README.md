# workflow の書き方（HEW2026 版・実物の ci.yml に注釈を付けたもの）

置き場所は必ず **リポジトリ直下の `.github/workflows/*.yml`**。
ここ以外に置いた YAML は GitHub に完全に無視される（`workflows` の s を忘れがち）。

★ の付いた行が「初心者がここで必ず転ぶ」箇所。

```yaml
name: CI                       # Actions タブに出る名前。日本語でもよい
on:                            # ★ いつ動かすか。無いと永遠に動かない
  push:
    branches: [main]
  pull_request:                # PR は全ブランチ
concurrency:                   # 同じブランチで連続 push したら古い実行を打ち切る
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:                          # ★ ここから下が本体。jobs → job ID → steps の 3 階層
  test:
    runs-on: ubuntu-latest     # どの Runner で動かすか
    timeout-minutes: 10        # 無限待ちの保険
    strategy:
      fail-fast: false         # 1 個失敗しても他は走らせる
      matrix:
        python-version: ["3.13"]   # ★ バージョンは文字列で。3.10 を 3.1 と読む事故を防ぐ
    steps:                     # 上から順に実行
      - uses: actions/checkout@v4      # ★ これが無いとコードが無い（空ディレクトリ）
      - uses: actions/setup-python@v5
        with:                          # ★ with はアクションへの引数
          python-version: ${{ matrix.python-version }}
          cache: pip                   # pip キャッシュを有効化
          cache-dependency-path: requirements.txt
      - name: Install dependencies     # run はシェルコマンド
        run: |                         # ★ 複数行は | （ブロックスカラー）
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - name: Pytest
        env:                           # ★ ステップ単位の環境変数
          SECRET_KEY: ci-dummy-secret-key   # ★ 本物の秘密は書かない
        run: pytest -q --cov=app --cov-report=term-missing
```

## 覚えることは 7 つだけ

| キー | 役割 | 典型例 |
|---|---|---|
| `on` | トリガー | `push` / `pull_request` / `workflow_dispatch` / `schedule` |
| `jobs.<id>` | ジョブ（並列実行の単位） | `test`, `deploy` |
| `runs-on` | 実行マシン | `ubuntu-latest`, `windows-latest`, `self-hosted` |
| `steps[].uses` | 既製アクションを使う | `actions/checkout@v4` |
| `steps[].run` | コマンドを実行 | `pytest -q` |
| `with` / `env` | 引数 / 環境変数 | `python-version`, `SECRET_KEY` |
| `needs` / `if` | 依存 / 条件 | テスト緑のときだけデプロイ |

## ★ 一番よく混同する 2 つ

```yaml
run: echo "${{ github.ref }}"     # ${{ }} … GitHub が「実行前」に文字列展開
run: echo "$GITHUB_REF"            # $VAR   … シェルが「実行時」に読む
```

`${{ }}` は workflow ファイルを書いた時点のテンプレート、`$VAR` はシェル変数。
**secret を `if:` の中に書くと動かない**（`if` はジョブ開始前に評価されるため）。
条件分岐に secret を使いたいときは、上の 05 のように `env` に入れて `run` の中で `[ -z "$HOOK" ]` する。

## よくある赤の原因（上から順に疑う）

1. **YAML のインデント** — タブ文字は禁止。スペース 2 個で統一。`- name:` の `-` の位置がずれると別構造になる。
1.5. **値の中のコロン** — `name: Ruff (blocking: 説明)` は構文エラーになる（`mapping values are not allowed here`）。値に `:` を入れるなら `name: "Ruff (blocking: 説明)"` と引用符で囲む。地味に一番よく踏む。
2. **`workflows` の綴り / 拡張子** — `.github/workflow/ci.yaml` は動くが `workflow`（単数）は無視される。`.yml` 推奨。
3. **checkout 忘れ** — `pytest: no tests ran` や `requirements.txt not found` はこれ。
4. **Python バージョン不一致** — ローカル 3.13、CI 3.11 だと構文エラーになりがち。`python-version` を揃える。
5. **`.env` 依存** — CI に `.env` は無い。テストに必要な値は `env:` で渡す。
6. **秘密情報を echo** — `run: echo ${{ secrets.X }}` はログに出る（伏字されない経路がある）。絶対にやらない。
7. **`pull_request_target`** — fork からの PR に secret を渡してしまう危険なトリガー。理解するまで使わない。

## デバッグの手順

```powershell
# 1. まずローカルで同じことをやる（これで 8 割解決する）
python -m pytest -q
python -m ruff check .

# 2. GitHub CLI があればログをターミナルで読める
gh run list
gh run view --log-failed

# 3. 手動実行（on: workflow_dispatch を書いておくと便利）
gh workflow run ci.yml
```

赤いログは**下から読む**。エラーの本体は最後の 20 行にあり、上は準備ログ。

## 練習（この順で、1 つずつ）

1. `01-minimal.yml` を `.github/workflows/` に置いて push → Actions タブで緑を見る
2. `02` に差し替え → わざとテストを 1 つ落として赤を見る（赤を見ないと CI は理解できない）
3. `03` でキャッシュを入れる → 2 回目のログで「cache hit」を確認
4. `04` でジョブを分ける → 並列で走る様子を確認
5. `05` で `needs` を外してみる → テストが赤でもデプロイが走る怖さを体感してから戻す
