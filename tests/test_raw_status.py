"""Полнота дня: чем кончилась каждая пара и можно ли грузить день."""
from __future__ import annotations

import config
import raw_status
from conftest import vacancies


def test_pair_files_are_ordered_by_page_not_by_name(write_raw):
    """p10 идёт после p2: по имени порядок был бы обратный."""
    for page in (1, 2, 10):
        write_raw("2026-09-17", "gb", "data engineer", page, vacancies(1, start=page * 100))

    pages = [raw_status.pair_files("2026-09-17", "gb", "data engineer")]
    names = [path.name for path in pages[0]]

    assert names == [
        "raw_2026-09-17_gb_data-engineer_p1.json",
        "raw_2026-09-17_gb_data-engineer_p2.json",
        "raw_2026-09-17_gb_data-engineer_p10.json",
    ]


def test_pair_without_files_is_not_complete(raw_dir):
    assert not raw_status.complete_by_files("2026-09-17", "gb", "data engineer")


def test_short_last_page_ends_the_pair(write_raw):
    write_raw("2026-09-17", "gb", "data engineer", 1, vacancies(12))
    assert raw_status.complete_by_files("2026-09-17", "gb", "data engineer")


def test_short_last_page_ends_the_pair_even_if_count_promised_more(write_raw):
    """count у Adzuna — оценка: пара кончается короткой страницей раньше него."""
    write_raw(
        "2026-09-17", "gb", "data engineer", 1, vacancies(12),
        count_reported=config.RESULTS_PER_PAGE,
    )
    assert raw_status.complete_by_files("2026-09-17", "gb", "data engineer")


def test_full_page_ends_the_pair_when_count_is_reached(write_raw):
    """Крупная выдача кончается полной страницей — одного признака мало."""
    write_raw(
        "2026-09-17", "gb", "data engineer", 1,
        vacancies(config.RESULTS_PER_PAGE),
        count_reported=config.RESULTS_PER_PAGE,
    )
    assert raw_status.complete_by_files("2026-09-17", "gb", "data engineer")


def test_missing_pages_leave_the_pair_incomplete(write_raw):
    write_raw(
        "2026-09-17", "gb", "data engineer", 1,
        vacancies(config.RESULTS_PER_PAGE),
        count_reported=500,
    )
    assert not raw_status.complete_by_files("2026-09-17", "gb", "data engineer")


def test_repeated_page_means_truncated_not_complete(write_raw):
    """За потолком Adzuna отдаёт ту же страницу, а не ошибку.

    count здесь сходится с числом разных вакансий, и без проверки на повтор
    пара объявлялась бы полной. Повтор весомее арифметики: он и есть потолок.
    """
    page = vacancies(config.RESULTS_PER_PAGE)
    write_raw("2026-09-17", "us", "data engineer", 1, page,
              count_reported=config.RESULTS_PER_PAGE)
    write_raw("2026-09-17", "us", "data engineer", 2, page,
              count_reported=config.RESULTS_PER_PAGE)

    assert not raw_status.complete_by_files("2026-09-17", "us", "data engineer")


def test_start_day_only_adds_expected_pairs(raw_dir):
    raw_status.start_day("2026-09-17", [("gb", "data engineer")])
    status = raw_status.start_day(
        "2026-09-17", [("gb", "data engineer"), ("de", "data analyst")]
    )

    assert status["expected_pairs"] == ["gb/data engineer", "de/data analyst"]


def test_record_pair_is_read_back(raw_dir):
    raw_status.start_day("2026-09-17", [("gb", "data engineer")])
    raw_status.record_pair(
        "2026-09-17", "gb", "data engineer", raw_status.COMPLETE,
        pages=3, collected=120, count_reported=120,
    )

    assert raw_status.pair_state("2026-09-17", "gb", "data engineer") == raw_status.COMPLETE
    assert raw_status.read_status("2026-09-17")["pairs"]["gb/data engineer"]["collected"] == 120


def test_pair_state_without_status_file_is_unknown(raw_dir):
    assert raw_status.pair_state("2026-09-17", "gb", "data engineer") is None


def test_expected_truncation_only_where_the_cap_was_known(raw_dir):
    assert raw_status.expected_truncation("us/data engineer", raw_status.TRUNCATED)
    assert not raw_status.expected_truncation("gb/data engineer", raw_status.TRUNCATED)
    assert not raw_status.expected_truncation("us/data engineer", raw_status.FAILED)


def test_day_is_complete_when_every_pair_finished(write_status):
    write_status(
        "2026-09-17",
        ["gb/data engineer", "us/data engineer"],
        {
            "gb/data engineer": {"status": raw_status.COMPLETE},
            # Ожидаемая обрезка США не держит взаперти остальные пары.
            "us/data engineer": {"status": raw_status.TRUNCATED},
        },
    )

    problems, source = raw_status.day_problems("2026-09-17")

    assert problems == []
    assert source == "status file"


def test_unexpected_truncation_blocks_the_day(write_status):
    write_status(
        "2026-09-17",
        ["gb/data engineer"],
        {"gb/data engineer": {"status": raw_status.TRUNCATED}},
    )

    problems, _ = raw_status.day_problems("2026-09-17")

    assert problems == ["gb/data engineer: truncated"]


def test_pair_never_started_blocks_the_day(write_status):
    write_status("2026-09-17", ["gb/data engineer"], {})

    problems, _ = raw_status.day_problems("2026-09-17")

    assert problems == ["gb/data engineer: not collected"]


def test_old_day_without_status_file_is_judged_by_files(write_raw):
    """Дни, собранные до появления журнала, оцениваются по самому сырью."""
    write_raw("2026-09-17", "gb", "data engineer", 1, vacancies(12))
    write_raw(
        "2026-09-17", "de", "data analyst", 1,
        vacancies(config.RESULTS_PER_PAGE, start=1000), count_reported=500,
    )
    # Обрезка США ожидаема и по файлам тоже не считается проблемой.
    write_raw(
        "2026-09-17", "us", "data engineer", 1,
        vacancies(config.RESULTS_PER_PAGE, start=2000), count_reported=7754,
    )

    problems, source = raw_status.day_problems("2026-09-17")

    assert problems == ["de/data analyst: incomplete by files"]
    assert source == "raw files, no status file"
