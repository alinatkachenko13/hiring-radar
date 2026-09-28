"""Общая обвязка тестов.

Сырьё подменяется на временную папку: модули проекта читают config.RAW_DIR
при каждом вызове, поэтому подмены атрибута в config достаточно и для
raw_files, и для raw_status, и для load.

Ключи Adzuna кладутся в окружение до импорта extract: он спрашивает их прямо
на импорте, и без них тест падал бы ещё до первой проверки. Значения
фиксированные, чтобы проверка маскировки не зависела от машины.
"""
from __future__ import annotations

import gzip
import json
import os
from pathlib import Path

import pytest

os.environ["ADZUNA_APP_ID"] = "test-app-id"
os.environ["ADZUNA_APP_KEY"] = "test-app-key"

import config  # noqa: E402  — только после ключей

FIXTURE_RAW = Path(__file__).parent / "fixtures" / "raw"


def vacancies(count: int, start: int = 1) -> list[dict]:
    """Вакансии с разными id — для проверок полноты пары."""
    return [{"id": str(start + number), "title": f"Vacancy {start + number}"}
            for number in range(count)]


@pytest.fixture
def raw_dir(tmp_path, monkeypatch) -> Path:
    """Пустая data/raw на время теста."""
    directory = tmp_path / "raw"
    directory.mkdir()
    monkeypatch.setattr(config, "RAW_DIR", directory)
    return directory


@pytest.fixture
def write_raw(raw_dir):
    """Кладёт страницу сырья в том же конверте, что пишет extract.py."""
    def write(
        run_date: str,
        country: str,
        role: str,
        page: int,
        results: list[dict],
        count_reported: int | None = None,
        gzipped: bool = False,
    ) -> Path:
        document = {
            "_meta": {
                "source": "adzuna",
                "run_date": run_date,
                "extracted_at": f"{run_date}T10:00:00+00:00",
                "country": country,
                "role_query": role,
                "page": page,
                "results_per_page": config.RESULTS_PER_PAGE,
                "max_days_old": config.window_for(country, role),
                "count_reported": len(results) if count_reported is None else count_reported,
            },
            "payload": {"results": results},
        }
        name = f"raw_{run_date}_{country}_{config.role_slug(role)}_p{page}.json"
        path = raw_dir / (name + ".gz" if gzipped else name)
        text = json.dumps(document, ensure_ascii=False)
        if gzipped:
            with gzip.open(path, "wt", encoding="utf-8") as handle:
                handle.write(text)
        else:
            path.write_text(text, encoding="utf-8")
        return path
    return write


@pytest.fixture
def write_status(raw_dir):
    """Журнал статусов дня: ожидаемые пары и чем кончилась каждая."""
    def write(run_date: str, expected: list[str], pairs: dict[str, dict]) -> Path:
        path = raw_dir / f"status_{run_date}.json"
        path.write_text(
            json.dumps({"run_date": run_date, "expected_pairs": expected, "pairs": pairs}),
            encoding="utf-8",
        )
        return path
    return write
