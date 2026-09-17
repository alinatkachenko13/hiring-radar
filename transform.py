"""dbt build с настройками GCP из .env.

config при импорте подставляет GCP_PROJECT, GCP_LOCATION и путь к ключу
в окружение, поэтому один и тот же запуск работает и с ноутбука,
и в контейнере планировщика.

Запуск:  python transform.py        цель prod (BigQuery)
         python transform.py dev    локальный DuckDB
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import config


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("DBT_TARGET", "prod")
    dbt = Path(sys.executable).with_name("dbt")
    command = [
        str(dbt) if dbt.exists() else "dbt",
        "build",
        "--profiles-dir", ".",
        "--target", target,
    ]
    print("Запуск:", " ".join(command[1:]))
    return subprocess.call(command, cwd=config.PROJECT_DIR / "dbt")


if __name__ == "__main__":
    sys.exit(main())
