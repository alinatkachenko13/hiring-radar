"""Короткая сводка о прогоне в Telegram.

Планировщик вызывает её последней задачей дня. Смысл — видеть, что проект жив
и как копится история, не заходя в интерфейс. О сбоях сообщают алерты, это
сообщение про нормальный ход дел.

Цифры берутся из двух источников: журнал статусов на диске говорит, как прошёл
сбор, витрины — что получилось на складе. Если склад недоступен, сводка всё
равно уходит: сбор мог пройти, а BigQuery лечь, и знать об этом полезно.

Запуск:  python daily_report.py
         python daily_report.py 2026-09-25
         python daily_report.py --dry-run   (напечатать, не отправляя)
"""
from __future__ import annotations

import sys
from datetime import date

import config
import raw_status
from notify import send_telegram


def fmt(number: int) -> str:
    """Разряды отделяются узким пробелом, а не запятой: в тексте запятые свои."""
    return f"{number:,}".replace(",", "\u202f")


def collection_line(run_date: str) -> str:
    """Как прошёл сбор, по журналу статусов."""
    status = raw_status.read_status(run_date)
    if status is None:
        return "Сбор: журнала статусов нет"

    pairs = status["pairs"]
    expected = len(status["expected_pairs"])
    complete = sum(1 for p in pairs.values() if p["status"] == raw_status.COMPLETE)
    vacancies = sum(p.get("collected") or 0 for p in pairs.values())

    line = f"Собрано: {complete} пар из {expected}, {fmt(vacancies)} вакансий"

    # Ожидаемая обрезка не сбой, но в сводке про неё честно сказать стоит.
    partial = [
        key for key, value in pairs.items()
        if value["status"] == raw_status.TRUNCATED
        and raw_status.expected_truncation(key, value["status"])
    ]
    if partial:
        line += f"\nЧастично (упёрлись в потолок выдачи): {', '.join(partial)}"

    other = [
        f"{key}: {value['status']}"
        for key, value in pairs.items()
        if value["status"] != raw_status.COMPLETE and key not in partial
    ]
    if other:
        line += "\nНе собрано: " + ", ".join(other)
    return line


def warehouse_lines(run_date: str) -> list[str]:
    """Что получилось на складе. Молчит, если склад недоступен."""
    try:
        from google.cloud import bigquery
    except ImportError:
        return []

    project = config.gcp_project()
    if not project:
        return []

    try:
        client = bigquery.Client(project=project, location=config.gcp_location())
        row = next(iter(client.query(f"""
            select
                count(*) as rows_total,
                countif(is_new) as new_ads,
                countif(is_gone) as gone_ads,
                countif(is_lifetime_tracked) as tracked
            from `{project}.marts.looker_vacancies`
            where observed_on = '{run_date}'
        """).result()))
    except Exception as error:  # склад недоступен — сводка всё равно уходит
        return [f"Склад недоступен: {type(error).__name__}"]

    if not row.rows_total:
        return ["Витрины: дня ещё нет, загрузка не дошла"]

    return [
        f"На витрине: {fmt(row.rows_total)} строк, из них под наблюдением {fmt(row.tracked)}",
        f"Новых: {fmt(row.new_ads)} · снято: {fmt(row.gone_ads)}",
    ]


def build_message(run_date: str) -> str:
    day = ".".join(reversed(run_date.split("-")[1:])) + "." + run_date[:4]
    parts = [f"hiring-radar, {day}", collection_line(run_date), *warehouse_lines(run_date)]
    return "\n".join(parts)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    run_date = args[0] if args else date.today().isoformat()
    message = build_message(run_date)

    if "--dry-run" in sys.argv:
        print(message)
        return 0

    # Сводка не должна ронять прогон: данные уже на складе.
    send_telegram(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
