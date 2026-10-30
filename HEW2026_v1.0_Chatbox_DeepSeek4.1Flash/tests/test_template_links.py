"""テンプレート内の url_for() が実在する endpoint を指しているか検査する.

今回の `url_for('points.charge')` → 正しくは `points.show_charge` のような
「画面を開くまで気づかない 500 エラー」を、CI で機械的に潰すためのテスト。
各ページを実際に開く巡回テストより速く、漏れが少ない。
"""

import re
from pathlib import Path

import pytest

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "app" / "templates"

# url_for('blueprint.view') / url_for("blueprint.view") の第 1 引数だけ拾う
URL_FOR_PATTERN = re.compile(r"""url_for\(\s*['"]([A-Za-z_][\w.]*)['"]""")

STATIC_ENDPOINTS = {"static"}


def _template_files():
    return sorted(TEMPLATE_DIR.rglob("*.html"))


def test_templates_exist():
    """テンプレートが見つからないと、このテスト自体が無意味になるので先に確認。"""

    assert _template_files(), f"テンプレートが見つかりません: {TEMPLATE_DIR}"


@pytest.mark.parametrize("template", _template_files(), ids=lambda p: p.name)
def test_all_url_for_targets_exist(app, template):
    text = template.read_text(encoding="utf-8")
    referenced = set(URL_FOR_PATTERN.findall(text))

    known = set(app.view_functions) | STATIC_ENDPOINTS
    missing = sorted(referenced - known)

    assert not missing, (
        f"{template.relative_to(TEMPLATE_DIR)} が存在しない endpoint を参照しています: "
        f"{missing}（利用可能な endpoint 例: "
        f"{sorted(e for e in known if e.startswith(missing[0].split('.')[0]))[:5]}）"
    )
