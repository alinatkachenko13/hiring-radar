"""Чтение файлов сырья с диска.

Сырьё лежит в двух видах: свежие дни как есть, старые сжаты gzip
(см. compress_raw.py). JSON жмётся примерно в десять раз, а перепись даёт
около 50 МБ в день, поэтому без сжатия диск сервера растёт на полтора
гигабайта в год.

Разницу между сжатым и обычным файлом знает только этот модуль. Остальной код
просит документ и получает словарь.
"""
from __future__ import annotations

import gzip
import json
import re
from pathlib import Path

import config

PAGE_RE = re.compile(r"_p(\d+)\.json(\.gz)?$")


def page_number(path: Path) -> int:
    """Номер страницы из имени файла. Для файлов без номера — 0."""
    match = PAGE_RE.search(path.name)
    return int(match.group(1)) if match else 0


def find(pattern: str) -> list[Path]:
    """Файлы сырья по шаблону имени без расширения, сжатые и обычные."""
    return sorted(
        [
            *config.RAW_DIR.glob(f"{pattern}.json"),
            *config.RAW_DIR.glob(f"{pattern}.json.gz"),
        ],
        key=lambda path: path.name,
    )


def read(path: Path) -> dict:
    """Документ сырья: конверт _meta + payload."""
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(path.read_text(encoding="utf-8"))
