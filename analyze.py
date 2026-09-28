"""Статистика по сохранённому сырью. К API не обращается.

Смысл разделения: замеры можно пересчитывать сколько угодно раз по одним и тем
же файлам, не тратя запросы и не рискуя получить другие данные.

Запуск:  python analyze.py [ГГГГ-ММ-ДД]
         без аргумента берётся последняя дата, найденная в data/raw
"""
import json
import sys
from collections import Counter, defaultdict

import raw_files
from config import RAW_DIR


def load_documents(run_date: str | None) -> tuple[str, list[dict]]:
    files = raw_files.find("raw_*")
    if not files:
        raise SystemExit(f"В {RAW_DIR} нет файлов. Сначала python extract.py")

    documents = [raw_files.read(path) for path in files]
    if run_date is None:
        run_date = max(doc["_meta"]["run_date"] for doc in documents)
    documents = [doc for doc in documents if doc["_meta"]["run_date"] == run_date]

    if not documents:
        raise SystemExit(f"Нет файлов за {run_date}")
    return run_date, documents


def flatten(documents: list[dict]) -> list[dict]:
    """Все вакансии одним списком, с проставленными страной и ролью запроса."""
    rows = []
    for doc in documents:
        meta = doc["_meta"]
        for vacancy in doc["payload"].get("results") or []:
            rows.append({
                "country": meta["country"],
                "role_query": meta["role_query"],
                # .get(), а не [] — необязательные поля приходят не всегда
                "id": vacancy.get("id"),
                "title": vacancy.get("title", ""),
                "company": (vacancy.get("company") or {}).get("display_name"),
                "salary_min": vacancy.get("salary_min"),
                "salary_max": vacancy.get("salary_max"),
                "salary_is_predicted": vacancy.get("salary_is_predicted"),
                "description": vacancy.get("description", ""),
            })
    return rows


def section(title: str) -> None:
    print(f"\n{title}\n{'-' * len(title)}")


def report_volume(rows: list[dict], documents: list[dict]) -> None:
    section("Объём: собрано записей (страна × роль)")
    reported = {}
    for doc in documents:
        meta = doc["_meta"]
        key = (meta["country"], meta["role_query"])
        reported[key] = meta["count_reported"]

    collected = Counter((row["country"], row["role_query"]) for row in rows)
    print(f"{'страна':<8}{'роль':<22}{'собрано':>9}{'count API':>11}")
    for key in sorted(reported):
        country, role = key
        print(f"{country:<8}{role:<22}{collected.get(key, 0):>9}{reported[key]:>11}")


def report_duplicates(rows: list[dict]) -> None:
    section("Дубли: пересечение выдач по ролям")
    ids = [row["id"] for row in rows if row["id"]]
    unique = len(set(ids))
    print(f"всего записей: {len(ids)}, уникальных id: {unique}, "
          f"дублей: {len(ids) - unique} ({(len(ids) - unique) / len(ids):.1%})")

    per_id = defaultdict(set)
    for row in rows:
        if row["id"]:
            per_id[row["id"]].add(row["role_query"])
    multi = Counter(len(roles) for roles in per_id.values())
    for roles_count in sorted(multi):
        print(f"  вакансий, найденных по {roles_count} запросам: {multi[roles_count]}")


def report_salary(rows: list[dict]) -> None:
    section("Раскрытие зарплат по странам")
    print("флаг = salary_is_predicted == '0'; вилка = salary_min присутствует")
    by_country = defaultdict(list)
    for row in rows:
        by_country[row["country"]].append(row)

    print(f"\n{'страна':<8}{'всего':>8}{'флаг':>8}{'вилка':>8}{'оба':>8}{'доля':>8}")
    for country in sorted(by_country):
        group = by_country[country]
        flag = sum(1 for row in group if row["salary_is_predicted"] == "0")
        band = sum(1 for row in group if row["salary_min"] is not None)
        both = sum(1 for row in group
                   if row["salary_is_predicted"] == "0" and row["salary_min"] is not None)
        share = both / len(group) if group else 0
        print(f"{country:<8}{len(group):>8}{flag:>8}{band:>8}{both:>8}{share:>7.1%}")


def report_title_duplicates(rows: list[dict]) -> None:
    section("Одинаковые объявления под разными id")
    seen = {}
    for row in rows:
        if row["id"] and row["id"] not in seen:
            seen[row["id"]] = row
    unique_rows = list(seen.values())

    pairs = Counter(
        (row["country"], row["company"], row["title"].strip())
        for row in unique_rows if row["company"] and row["title"]
    )
    repeated = {key: number for key, number in pairs.items() if number > 1}
    extra = sum(number - 1 for number in repeated.values())
    print(f"уникальных id: {len(unique_rows)}")
    print(f"из них с повторяющейся парой компания+тайтл: {extra} "
          f"({extra / len(unique_rows):.1%})")
    print("топ повторов:")
    for (country, company, title), number in Counter(repeated).most_common(8):
        print(f"  {number:>4}  {country}  {company} — {title}")


def report_titles(rows: list[dict], top: int = 15) -> None:
    section(f"Фактические тайтлы: топ-{top} (сырьё для dim_role)")
    titles = Counter(row["title"].strip() for row in rows if row["title"])
    for title, number in titles.most_common(top):
        print(f"  {number:>4}  {title}")


def report_skills(rows: list[dict]) -> None:
    section("Технологии в обрезанных описаниях (оценка потолка)")
    tech = ["python", "sql", "spark", "airflow", "dbt", "aws", "azure", "gcp",
            "kafka", "snowflake", "docker", "kubernetes", "tableau", "power bi"]
    total = len(rows)
    hits = Counter()
    any_hit = 0
    for row in rows:
        text = row["description"].lower()
        found = [name for name in tech if name in text]
        hits.update(found)
        if found:
            any_hit += 1
    print(f"описаний с хотя бы одной технологией: {any_hit} из {total} "
          f"({any_hit / total:.1%})")
    for name, number in hits.most_common():
        print(f"  {name:<12}{number:>5}  {number / total:>6.1%}")


def report_quota(documents: list[dict]) -> None:
    section("Заголовки ответа: есть ли остаток квоты")
    headers = documents[0]["_meta"].get("response_headers", {})
    interesting = {k: v for k, v in headers.items()
                   if any(word in k.lower() for word in
                          ("limit", "quota", "remain", "ratelimit"))}
    print(interesting if interesting else "  квоту в заголовках API не отдаёт")


def main() -> None:
    run_date = sys.argv[1] if len(sys.argv) > 1 else None
    run_date, documents = load_documents(run_date)
    rows = flatten(documents)
    print(f"Дата сбора: {run_date}, файлов: {len(documents)}, записей: {len(rows)}")

    report_volume(rows, documents)
    report_duplicates(rows)
    report_salary(rows)
    report_title_duplicates(rows)
    report_titles(rows)
    report_skills(rows)
    report_quota(documents)


if __name__ == "__main__":
    main()
