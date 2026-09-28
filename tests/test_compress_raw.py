"""Дата в имени файла сырья."""
from __future__ import annotations

from datetime import date

import pytest

import compress_raw


@pytest.mark.parametrize("name, expected", [
    ("raw_2026-09-23_gb_data-engineer_p1.json", date(2026, 9, 23)),
    ("raw_2026-09-23_gb_data-engineer_p1.json.gz", date(2026, 9, 23)),
    ("status_2026-09-23.json", None),   # не сырьё: даты в этом месте нет
    ("README.md", None),
    ("raw_не-дата_gb_p1.json", None),
])
def test_day_of(name, expected):
    assert compress_raw.day_of(name) == expected
