"""Сводка по витринам после dbt build. К API не ходит.

Сверяет склад с цифрами analyze.py: сколько записей, сколько уникальных id,
как сработал фильтр роли, раскрытие зарплат.

Запуск:  python report_marts.py
"""
from collections import defaultdict

import duckdb

from config import DUCKDB_PATH


def section(title: str) -> None:
    print(f"\n{title}\n{'-' * len(title)}")


def main() -> None:
    if not DUCKDB_PATH.exists():
        raise SystemExit(
            f"Нет {DUCKDB_PATH}. Сначала python load.py и dbt build в каталоге dbt."
        )

    conn = duckdb.connect(str(DUCKDB_PATH), read_only=True)

    raw_n, raw_ids = conn.execute(
        "select count(*), count(distinct source_id) from raw.adzuna_results"
    ).fetchone()
    stg_n = conn.execute("select count(*) from staging.stg_vacancies").fetchone()[0]
    dedup_n, dedup_ids = conn.execute(
        """
        select count(*), count(distinct source_id)
        from intermediate.int_vacancies_deduped
        """
    ).fetchone()
    relevant_n, other_n = conn.execute(
        """
        select
            count(*) filter (where is_relevant),
            count(*) filter (where not is_relevant)
        from intermediate.int_vacancies_enriched
        """
    ).fetchone()

    section("Слой за слоем")
    print(f"raw строк / уникальных id:     {raw_n} / {raw_ids}")
    print(f"staging строк:                 {stg_n}")
    print(f"после дедупа по id:            {dedup_n} (уникальных id {dedup_ids})")
    print(f"релевантных / other:           {relevant_n} / {other_n}")
    if dedup_n:
        print(f"доля other:                    {other_n / dedup_n:.1%}")

    section("Витрина рынка: объявления и позиции")
    rows = conn.execute(
        """
        select
            country_code,
            role_key,
            sum(n_ads) as n_ads,
            sum(n_positions) as n_positions,
            sum(n_new) as n_new,
            sum(n_gone) as n_gone
        from marts.mart_market_daily
        group by country_code, role_key
        order by country_code, role_key
        """
    ).fetchall()
    print(f"{'страна':<8}{'роль':<22}{'объявл.':>9}{'позиции':>9}{'новые':>8}{'ушли':>8}")
    by_country = defaultdict(lambda: [0, 0])
    for country, role, ads, positions, new, gone in rows:
        print(f"{country:<8}{role:<22}{ads:>9}{positions:>9}{new:>8}{gone:>8}")
        by_country[country][0] += ads
        by_country[country][1] += positions
    print()
    for country in sorted(by_country):
        ads, positions = by_country[country]
        print(f"  итог {country}: {ads} объявлений, {positions} позиций")

    section("Раскрытие зарплат (релевантные, не gone)")
    print(f"{'страна':<8}{'объявл.':>9}{'с вилкой':>10}{'доля':>8}")
    for country, ads, disclosed in conn.execute(
        """
        select
            country_code,
            n_ads,
            n_salary_disclosed
        from marts.mart_salary_disclosure
        order by country_code
        """
    ).fetchall():
        share = disclosed / ads if ads else 0
        print(f"{country:<8}{ads:>9}{disclosed:>10}{share:>7.1%}")

    section("Зарплатная витрина (только страны с show_salary)")
    salary_rows = conn.execute(
        """
        select country_code, role_key, n_disclosed, round(salary_mid_p50, 0)
        from marts.mart_salary_daily
        order by country_code, role_key
        """
    ).fetchall()
    if not salary_rows:
        print("  пусто — на этой дате нет gb/us с раскрытой вилкой, либо витрина не собралась")
    else:
        print(f"{'страна':<8}{'роль':<22}{'n':>6}{'медиана':>10}")
        for country, role, n, median in salary_rows:
            print(f"{country:<8}{role:<22}{n:>6}{median:>10.0f}")

    section("Топ тайтлов, которые фильтр роли выкинул")
    unmatched = conn.execute(
        """
        select n, country_code, title
        from marts.mart_qa_unmatched_titles
        order by n desc
        limit 15
        """
    ).fetchall()
    for n, country, title in unmatched:
        print(f"  {n:>4}  {country}  {title}")

    conn.close()


if __name__ == "__main__":
    main()
