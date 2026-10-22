"""Чтение сырья: сжатые и обычные файлы неразличимы для остального кода."""
from __future__ import annotations

from pathlib import Path

import pytest

import raw_files


@pytest.mark.parametrize("name, expected", [
    ("raw_2026-09-17_gb_data-engineer_p1.json", 1),
    ("raw_2026-09-17_gb_data-engineer_p12.json.gz", 12),
    ("status_2026-09-17.json", 0),
])
def test_page_number_from_file_name(name, expected):
    assert raw_files.page_number(Path(name)) == expected


def test_find_returns_compressed_and_plain(write_raw):
    write_raw("2026-09-17", "gb", "data engineer", 1, [])
    write_raw("2026-09-17", "gb", "data engineer", 2, [], gzipped=True)
    write_raw("2026-09-18", "gb", "data engineer", 1, [])

    found = [path.name for path in raw_files.find("raw_2026-09-17_gb_data-engineer_p*")]

    assert found == [
        "raw_2026-09-17_gb_data-engineer_p1.json",
        "raw_2026-09-17_gb_data-engineer_p2.json.gz",
    ]


def test_read_is_the_same_for_compressed_and_plain(write_raw):
    plain = write_raw("2026-09-17", "gb", "data engineer", 1, [{"id": "1"}])
    packed = write_raw("2026-09-17", "gb", "data engineer", 1, [{"id": "1"}], gzipped=True)

    assert raw_files.read(plain) == raw_files.read(packed)
    assert raw_files.read(packed)["payload"]["results"] == [{"id": "1"}]
