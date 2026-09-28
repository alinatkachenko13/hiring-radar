"""Сборка tests/fixtures/raw из настоящего сырья для CI.

Два дня, шесть пар страна-роль, по 12 объявлений на файл: 8 есть в оба дня,
по 4 только в один. Так в витринах появляются новые и ушедшие объявления.
Каждый файл — одна неполная страница, поэтому load.py считает пару полной.

Правки поверх сырья:
- app_id в utm_source ссылок заменён на "fixture";
- у первого общего объявления первой пары во второй день изменён contract_time,
  чтобы dim_vacancy получил вторую версию (SCD2).

Нужны оба дня в data/raw. Запуск: python tests/fixtures/make_fixtures.py
"""
import json
import re
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
RAW = PROJECT_DIR / "data" / "raw"
OUT = Path(__file__).resolve().parent / "raw"
DAYS = ("2026-09-17", "2026-09-18")
PAIRS = [
    ("gb", "data-engineer"),
    ("gb", "analytics-engineer"),
    ("gb", "data-analyst"),
    ("gb", "data-scientist"),
    ("de", "data-engineer"),
    ("de", "analytics-engineer"),
]
N_COMMON, N_ONLY = 8, 4


def pair_pages(day: str, country: str, role: str) -> list[Path]:
    return sorted(
        RAW.glob(f"raw_{day}_{country}_{role}_p*.json"),
        key=lambda path: int(path.stem.rsplit("_p", 1)[1]),
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for country, role in PAIRS:
        first_page, by_id = {}, {}
        for day in DAYS:
            pages = pair_pages(day, country, role)
            first_page[day] = json.loads(pages[0].read_text(encoding="utf-8"))
            by_id[day] = {}
            for page in pages:
                for vacancy in json.loads(page.read_text(encoding="utf-8"))["payload"].get("results") or []:
                    by_id[day].setdefault(str(vacancy["id"]), vacancy)

        common = sorted(set(by_id[DAYS[0]]) & set(by_id[DAYS[1]]))[:N_COMMON]
        for i, day in enumerate(DAYS):
            other = by_id[DAYS[1 - i]]
            only = sorted(key for key in by_id[day] if key not in other)[:N_ONLY]
            results = [dict(by_id[day][key]) for key in common + only]
            if i == 1 and (country, role) == PAIRS[0]:
                before = results[0].get("contract_time")
                results[0]["contract_time"] = "part_time" if before != "part_time" else "full_time"

            document = first_page[day]
            document["_meta"].update(page=1, count_reported=len(results))
            document["payload"]["results"] = results
            document["payload"]["count"] = len(results)
            text = json.dumps(document, ensure_ascii=False, indent=1) + "\n"
            text = re.sub(r'utm_source=[^&"]+', "utm_source=fixture", text)
            path = OUT / f"raw_{day}_{country}_{role}_p1.json"
            path.write_text(text, encoding="utf-8")
            print(f"{path.name}: {len(common)} общих, {len(only)} только в этот день")


if __name__ == "__main__":
    main()
