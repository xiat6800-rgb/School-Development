"""workflow YAML の構文チェック（GitHub に push する前にローカルで確認する用）.

使い方:  python check_workflows.py <yml があるディレクトリ>
"""

import sys
from pathlib import Path

import yaml


def main(directory: str) -> int:
    files = sorted(Path(directory).glob("*.yml")) + sorted(Path(directory).glob("*.yaml"))
    if not files:
        print(f"YAML がありません: {directory}")
        return 1

    errors = 0
    for path in files:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            print(f"[NG] {path.name}: YAML 構文エラー\n{exc}")
            errors += 1
            continue

        if not isinstance(data, dict):
            print(f"[NG] {path.name}: 中身が辞書ではありません")
            errors += 1
            continue

        # YAML 1.1 では on: が真偽値 True になるので両方許容する
        trigger = data.get("on", data.get(True))
        jobs = data.get("jobs")

        problems = []
        if trigger is None:
            problems.append("on: が無い（workflow が動かない）")
        if not isinstance(jobs, dict) or not jobs:
            problems.append("jobs: が無い")
        else:
            for job_id, job in jobs.items():
                if not isinstance(job, dict):
                    problems.append(f"jobs.{job_id} が辞書でない")
                    continue
                if "runs-on" not in job and "uses" not in job:
                    problems.append(f"jobs.{job_id} に runs-on が無い")
                if "steps" not in job and "uses" not in job:
                    problems.append(f"jobs.{job_id} に steps が無い")

        if problems:
            print(f"[NG] {path.name}: " + " / ".join(problems))
            errors += 1
        else:
            print(f"[OK] {path.name}: jobs={list(jobs)}")

    print(f"\n{len(files) - errors} / {len(files)} OK")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
