"""Разбор сырья в строки склада."""
from __future__ import annotations

import json

import pytest

import load
from conftest import FIXTURE_RAW, vacancies


def test_location_parts_takes_region_and_city_from_area():
    vacancy = {"location": {
        "display_name": "Berlin, Deutschland",
        "area": ["Deutschland", "Berlin", "Berlin Mitte"],
    }}

    display_name, region, city, area_json = load.location_parts(vacancy)

    assert display_name == "Berlin, Deutschland"
    assert region == "Berlin"
    assert city == "Berlin Mitte"
    assert json.loads(area_json) == ["Deutschland", "Berlin", "Berlin Mitte"]


def test_location_parts_without_area_leaves_region_empty():
    """Страна без уточнения — не регион и не город."""
    display_name, region, city, area_json = load.location_parts(
        {"location": {"display_name": "Deutschland", "area": ["Deutschland"]}}
    )

    assert (display_name, region, city) == ("Deutschland", None, None)
    assert json.loads(area_json) == ["Deutschland"]


def test_location_parts_without_location_does_not_fail():
    assert load.location_parts({}) == (None, None, None, "[]")


def test_flatten_file_keeps_the_envelope_fields():
    rows = load.flatten_file(FIXTURE_RAW / "raw_2026-09-17_de_data-engineer_p1.json")

    assert len(rows) == 12
    row = rows[0]
    assert row["run_date"] == "2026-09-17"
    assert row["country"] == "de"
    assert row["role_query"] == "data engineer"
    assert row["source_file"] == "raw_2026-09-17_de_data-engineer_p1.json"
    assert isinstance(row["source_id"], str)
    # Вакансия целиком остаётся в строке: слой сырья ничего не теряет.
    assert json.loads(row["vacancy_json"])["id"] == row["source_id"]


def test_flatten_file_trims_empty_company_to_null(write_raw):
    path = write_raw("2026-09-17", "gb", "data engineer", 1, [
        {"id": "1", "company": {"display_name": "  "}},
        {"id": "2", "company": {"display_name": " Soda Data "}},
    ])

    rows = load.flatten_file(path)

    assert rows[0]["company_name"] is None
    assert rows[1]["company_name"] == "Soda Data"


def test_collect_rows_takes_only_the_asked_day(write_raw):
    write_raw("2026-09-17", "gb", "data engineer", 1, vacancies(3))
    write_raw("2026-09-18", "gb", "data engineer", 1, vacancies(5, start=100))

    rows, files = load.collect_rows("2026-09-18")

    assert len(rows) == 5
    assert [path.name for path in files] == ["raw_2026-09-18_gb_data-engineer_p1.json"]
    assert {row["run_date"] for row in rows} == {"2026-09-18"}


def test_collect_rows_without_files_says_what_to_run(raw_dir):
    with pytest.raises(SystemExit, match="extract.py"):
        load.collect_rows("2026-09-18")
