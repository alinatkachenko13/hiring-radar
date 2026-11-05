"""Когда объявление считается снятым: сценарии на настоящем dbt и DuckDB.

Правило живёт в SQL (int_vacancy_daily), и проверить его можно, только прогнав
модели. Сырьё шести дней собирается в мини-склад тем же load.py, что и на
складе, dbt строит промежуточные модели, тест читает is_gone.

Три пары:
- ca / data analyst переписывается все шесть дней, id 6 снят после второго дня;
- ca / data engineer три дня переписывается, потом уходит на поток с окном. Это
  то, что случилось с ним 05.11.2026, когда запас перерос потолок выдачи, а
  остальные роли Канады продолжали перепись;
- de / data analyst переписывается, но в третий день перепись обрезана потолком
  (truncated): часть объявлений просто не попала в выдачу.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest
from _pytest.monkeypatch import MonkeyPatch

import config
import load

PROJECT = Path(__file__).resolve().parents[1]
DBT = Path(sys.executable).with_name("dbt")
DAYS = [f"2026-10-{day:02d}" for day in range(1, 7)]


class Scenario:
    """Сырьё и журнал статусов шести дней во временной data/raw."""

    def __init__(self, raw: Path):
        self.raw = raw
        self.verdicts: dict[str, dict[str, str]] = {day: {} for day in DAYS}

    def pair(self, day: str, country: str, role: str, ids: list[int], title: str,
             window: int | None = None, verdict: str = "complete") -> None:
        results = [{"id": str(n), "title": title, "created": "2026-09-30T08:00:00Z"}
                   for n in ids]
        document = {
            "_meta": {
                "source": "adzuna", "run_date": day, "extracted_at": f"{day}T10:00:00+00:00",
                "country": country, "role_query": role, "page": 1,
                "results_per_page": config.RESULTS_PER_PAGE, "max_days_old": window,
                "count_reported": len(results),
            },
            "payload": {"results": results},
        }
        name = f"raw_{day}_{country}_{config.role_slug(role)}_p1.json"
        (self.raw / name).write_text(json.dumps(document), encoding="utf-8")
        self.verdicts[day][f"{country}/{role}"] = verdict

    def write_statuses(self) -> None:
        for day, pairs in self.verdicts.items():
            status = {
                "run_date": day,
                "expected_pairs": list(pairs),
                "pairs": {key: {"status": verdict} for key, verdict in pairs.items()},
            }
            (self.raw / f"status_{day}.json").write_text(json.dumps(status), encoding="utf-8")


def fill(scenario: Scenario) -> None:
    for number, day in enumerate(DAYS, start=1):
        # ca / data analyst: ids 1–5 живут все дни, id 6 пропал после второго.
        scenario.pair(day, "ca", "data analyst",
                      list(range(1, 6)) + ([6] if number <= 2 else []), "Data Analyst")

        # ca / data engineer: ids 101–105 на переписи, дальше только свежий 101 в окне.
        if number <= 3:
            scenario.pair(day, "ca", "data engineer", list(range(101, 106)), "Data Engineer")
        else:
            scenario.pair(day, "ca", "data engineer", [101], "Data Engineer", window=2)

        # de / data analyst: ids 201–205; на третий день перепись обрезана и
        # вернула только 201–203, потом выдача снова полная, но без 204 и 205.
        if number <= 2:
            scenario.pair(day, "de", "data analyst", list(range(201, 206)), "Data Analyst")
        elif number == 3:
            scenario.pair(day, "de", "data analyst", [201, 202, 203], "Data Analyst",
                          verdict="truncated")
        else:
            scenario.pair(day, "de", "data analyst", [201, 202, 203], "Data Analyst")
    scenario.write_statuses()


def run_dbt(database: Path, workdir: Path) -> None:
    profiles = workdir / "profiles"
    profiles.mkdir()
    (profiles / "profiles.yml").write_text(
        "hiring_radar:\n  target: dev\n  outputs:\n    dev:\n      type: duckdb\n"
        f"      path: {database.as_posix()}\n      threads: 2\n",
        encoding="utf-8",
    )
    done = subprocess.run(
        [str(DBT), "run", "--select", "+int_vacancy_daily",
         "--project-dir", str(PROJECT / "dbt"), "--profiles-dir", str(profiles),
         "--target-path", str(workdir / "target"), "--log-path", str(workdir / "logs")],
        capture_output=True, text=True,
    )
    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-1000:]


@pytest.fixture(scope="module")
def gone(tmp_path_factory) -> dict[str, str]:
    """id → первый день, в который объявление признано снятым. Нет id — не снято."""
    if not DBT.exists():
        pytest.skip("dbt не установлен")
    workdir = tmp_path_factory.mktemp("scenario")
    raw = workdir / "raw"
    raw.mkdir()
    database = workdir / "scenario.duckdb"

    with MonkeyPatch.context() as patch:
        patch.setattr(config, "RAW_DIR", raw)
        patch.setattr(load, "DUCKDB_PATH", database)
        patch.setattr(load, "WAREHOUSE_DIR", workdir)
        fill(Scenario(raw))
        rows, _ = load.collect_rows(None)
        jsonl = workdir / "rows.jsonl"
        load.write_jsonl(rows, jsonl)
        load.load_duckdb(jsonl, DAYS)

    run_dbt(database, workdir)
    connection = duckdb.connect(str(database), read_only=True)
    try:
        found = connection.execute(
            "select source_id, min(observed_on)::varchar from intermediate.int_vacancy_daily "
            "where is_gone group by 1"
        ).fetchall()
    finally:
        connection.close()
    return dict(found)


def test_ad_that_really_left_a_censused_pair_is_gone(gone):
    """Контроль: правило не сломано, настоящая пропажа по-прежнему видна.

    id 6 видели переписью на второй день, дважды подряд его нет, а пара
    переписывалась и вчера, и сегодня.
    """
    assert gone.get("6") == DAYS[3]


def test_ads_of_a_pair_that_switched_to_flow_are_not_called_gone(gone):
    """Ради этого и правка: 102–105 нет в оконной выдаче, но их никто не снимал.

    Страна ca при этом продолжает перепись другими парами, и прежняя проверка
    «страна переписывалась» принимала такую пропажу за закрытие.
    """
    assert not {"102", "103", "104", "105"} & set(gone)


def test_truncated_census_day_is_not_evidence_of_closure(gone):
    """В третий день перепись de обрезана: 204 и 205 в выдачу просто не попали."""
    assert not {"204", "205"} & set(gone)
