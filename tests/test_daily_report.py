"""Сводка о прогоне: что уходит в Telegram."""
from __future__ import annotations

import daily_report
import raw_status


def test_fmt_separates_thousands_without_commas():
    """Запятые в сводке свои, поэтому разряды отделяются узким пробелом."""
    assert daily_report.fmt(1234567) == "1 234 567"
    assert daily_report.fmt(120) == "120"


def test_collection_line_without_status_file(raw_dir):
    assert daily_report.collection_line("2026-09-17") == "Сбор: журнала статусов нет"


def test_expected_truncation_counts_as_collected(write_status):
    """«29 из 30» читалось как поломка, хотя сбора это не касается."""
    write_status(
        "2026-09-17",
        ["gb/data engineer", "us/data engineer"],
        {
            "gb/data engineer": {"status": raw_status.COMPLETE, "collected": 120},
            "us/data engineer": {
                "status": raw_status.TRUNCATED, "collected": 5000, "count_reported": 7754,
            },
        },
    )

    line = daily_report.collection_line("2026-09-17")

    assert "Собрано: 2 пар из 2" in line
    assert "5 120 вакансий" in line
    assert "us/data engineer: 5 000 из 7 754" in line
    assert "Не собрано" not in line


def test_failed_pair_is_named_in_the_summary(write_status):
    write_status(
        "2026-09-17",
        ["gb/data engineer", "de/data analyst"],
        {
            "gb/data engineer": {"status": raw_status.COMPLETE, "collected": 120},
            "de/data analyst": {"status": raw_status.FAILED, "collected": 0},
        },
    )

    line = daily_report.collection_line("2026-09-17")

    assert "Собрано: 1 пар из 2" in line
    assert "Не собрано: de/data analyst: failed" in line
