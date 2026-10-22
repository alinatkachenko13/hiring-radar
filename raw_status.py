"""Статусы пар страна-роль за день сбора.

extract.py пишет data/raw/status_<дата>.json по ходу работы: какие пары ожидались
и чем закончилась каждая (complete, failed, truncated). load.py читает этот файл
и грузит день, только если все ожидаемые пары complete.

Дни, собранные до появления файла статусов, оцениваются по самим файлам сырья:
пары берутся из _meta, полнота пары считается тем же правилом, что в сборе.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import config
import raw_files

COMPLETE = "complete"
FAILED = "failed"
TRUNCATED = "truncated"


def pair_key(country: str, role: str) -> str:
    return f"{country}/{role}"


def status_path(run_date: str) -> Path:
    return config.RAW_DIR / f"status_{run_date}.json"


def pair_files(run_date: str, country: str, role: str) -> list[Path]:
    """Файлы пары за дату, по возрастанию номера страницы."""
    pattern = f"raw_{run_date}_{country}_{config.role_slug(role)}_p*"
    return sorted(raw_files.find(pattern), key=raw_files.page_number)


def complete_by_files(run_date: str, country: str, role: str) -> bool:
    """Собрана ли пара до конца, судя по файлам.

    Признаков конца два, ровно те же, что при сборе: последняя страница неполная,
    либо набрано не меньше, чем обещал count. Крупные выдачи заканчиваются полной
    страницей, поэтому одного признака неполной страницы мало.
    """
    files = pair_files(run_date, country, role)
    if not files:
        return False

    # Считаются разные вакансии: за потолком выдачи Adzuna повторяет одну и ту же
    # страницу, и арифметика «номер страницы × размер» такую пару объявляла полной.
    seen: set[str] = set()
    results: list = []
    last = None
    for path in files:
        last = raw_files.read(path)
        results = last["payload"].get("results") or []
        ids = {item["id"] for item in results if item.get("id")}
        if results and not ids - seen:
            return False    # страница без новых вакансий: пара обрезана потолком
        seen |= ids

    if len(results) < config.RESULTS_PER_PAGE:
        return True
    return len(seen) >= last["_meta"]["count_reported"]


def read_status(run_date: str) -> dict | None:
    path = status_path(run_date)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write(run_date: str, status: dict) -> None:
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    status["updated_at"] = datetime.now(timezone.utc).isoformat()
    path = status_path(run_date)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def start_day(run_date: str, pairs: list[tuple[str, str]]) -> dict:
    """Фиксирует ожидаемые пары дня. Повторный запуск только дополняет список."""
    status = read_status(run_date) or {"run_date": run_date, "expected_pairs": [], "pairs": {}}
    for country, role in pairs:
        key = pair_key(country, role)
        if key not in status["expected_pairs"]:
            status["expected_pairs"].append(key)
    _write(run_date, status)
    return status


def record_pair(
    run_date: str,
    country: str,
    role: str,
    state: str,
    pages: int | None = None,
    collected: int | None = None,
    count_reported: int | None = None,
) -> None:
    status = read_status(run_date) or start_day(run_date, [(country, role)])
    status["pairs"][pair_key(country, role)] = {
        "status": state,
        "pages": pages,
        "collected": collected,
        "count_reported": count_reported,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    _write(run_date, status)


def pair_state(run_date: str, country: str, role: str) -> str | None:
    status = read_status(run_date)
    if status is None:
        return None
    return status["pairs"].get(pair_key(country, role), {}).get("status")


def expected_truncation(key: str, state: str | None) -> bool:
    """Обрезка пары, которая и не могла поместиться в потолок выдачи.

    Такая пара не блокирует день: иначе одна пара США держала бы взаперти
    остальные двадцать девять (см. config.PARTIAL_PAIRS).
    """
    if state != TRUNCATED:
        return False
    country, _, role = key.partition("/")
    return config.is_partial_pair(country, role)


def day_problems(run_date: str) -> tuple[list[str], str]:
    """Что мешает считать день полным. Пустой список: день полный.

    Второе значение говорит, откуда взято решение: из файла статусов или из файлов
    сырья (для дней, собранных до появления статусов).
    """
    status = read_status(run_date)
    if status is not None:
        problems = []
        for key in status["expected_pairs"]:
            state = status["pairs"].get(key, {}).get("status")
            if state == COMPLETE or expected_truncation(key, state):
                continue
            problems.append(f"{key}: {state or 'not collected'}")
        return problems, "status file"

    pairs = set()
    for path in raw_files.find(f"raw_{run_date}_*"):
        meta = raw_files.read(path)["_meta"]
        pairs.add((meta["country"], meta["role_query"]))
    problems = [
        f"{pair_key(country, role)}: incomplete by files"
        for country, role in sorted(pairs)
        if not complete_by_files(run_date, country, role)
        and not config.is_partial_pair(country, role)
    ]
    return problems, "raw files, no status file"
