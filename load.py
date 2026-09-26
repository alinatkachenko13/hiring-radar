"""Загрузка сырья с диска на склад.

Файлы в data/raw не трогаются: это неизменяемый слой. Скрипт читает конверты
_meta + payload и кладёт по одной строке на вакансию в таблицу raw.adzuna_results.

По умолчанию склад — локальный DuckDB, чтобы блок 1 можно было проверить без GCP.
BigQuery: python load.py --backend bigquery (нужен GCP_PROJECT).

Грузится только полный день: все пары страна-роль собраны до конца
(см. raw_status.py). Неполный день пропускается, скрипт завершается с кодом 1.
Загрузить неполный день вручную: --allow-incomplete.

Запуск:  python load.py
         python load.py 2026-09-01
         python load.py --backend bigquery
         python load.py 2026-09-01 --allow-incomplete
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import raw_files
import raw_status
from config import (
    BQ_RAW_DATASET,
    BQ_RAW_TABLE,
    DUCKDB_PATH,
    RAW_DIR,
    WAREHOUSE_DIR,
    gcp_location,
    gcp_project,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Сырьё с диска → склад")
    parser.add_argument(
        "run_date",
        nargs="?",
        help="YYYY-MM-DD, по умолчанию все даты в data/raw",
    )
    parser.add_argument(
        "--backend",
        choices=("duckdb", "bigquery"),
        default="duckdb",
        help="duckdb — локально, bigquery — облако",
    )
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="загрузить день, даже если не все пары собраны полностью",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="оставить промежуточные jsonl на диске (для отладки)",
    )
    return parser.parse_args()


def location_parts(vacancy: dict) -> tuple[str | None, str | None, str | None, str]:
    location = vacancy.get("location") or {}
    area = location.get("area") or []
    region = area[1] if len(area) > 1 else None
    city = area[-1] if len(area) > 1 else None
    return (
        location.get("display_name"),
        region,
        city,
        json.dumps(area, ensure_ascii=False),
    )


def flatten_file(path: Path) -> list[dict]:
    document = raw_files.read(path)
    meta = document["_meta"]
    rows = []
    for vacancy in document.get("payload", {}).get("results") or []:
        display_name, region, city, area_json = location_parts(vacancy)
        company = vacancy.get("company") or {}
        category = vacancy.get("category") or {}
        rows.append({
            "source_file": path.name,
            "run_date": meta["run_date"],
            "extracted_at": meta.get("extracted_at"),
            "country": meta["country"],
            "role_query": meta["role_query"],
            "page": meta.get("page"),
            "results_per_page": meta.get("results_per_page"),
            "max_days_old": meta.get("max_days_old"),
            "count_reported": meta.get("count_reported"),
            "source_id": str(vacancy["id"]) if vacancy.get("id") is not None else None,
            "title": vacancy.get("title"),
            "description": vacancy.get("description"),
            "posted_at": vacancy.get("created"),
            "company_name": (company.get("display_name") or "").strip() or None,
            "salary_min": vacancy.get("salary_min"),
            "salary_max": vacancy.get("salary_max"),
            "salary_is_predicted": vacancy.get("salary_is_predicted"),
            "contract_type": vacancy.get("contract_type"),
            "contract_time": vacancy.get("contract_time"),
            "location_display_name": display_name,
            "location_region": region,
            "location_city": city,
            "location_area_json": area_json,
            "latitude": vacancy.get("latitude"),
            "longitude": vacancy.get("longitude"),
            "category_tag": category.get("tag"),
            "category_label": category.get("label"),
            "redirect_url": vacancy.get("redirect_url"),
            "vacancy_json": json.dumps(vacancy, ensure_ascii=False),
        })
    return rows


def collect_rows(run_date: str | None) -> tuple[list[dict], list[Path]]:
    files = raw_files.find("raw_*")
    if run_date:
        files = [path for path in files if path.name.startswith(f"raw_{run_date}_")]
    if not files:
        where = f" за {run_date}" if run_date else ""
        raise SystemExit(f"В {RAW_DIR} нет файлов{where}. Сначала python extract.py")

    rows = []
    for path in files:
        rows.extend(flatten_file(path))
    return rows, files


def write_jsonl(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_duckdb(jsonl_path: Path, run_dates: list[str]) -> None:
    import duckdb

    WAREHOUSE_DIR.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(DUCKDB_PATH))
    conn.execute("create schema if not exists raw")
    conn.execute(
        """
        create table if not exists raw.adzuna_results (
            source_file varchar,
            run_date date,
            extracted_at timestamp,
            country varchar,
            role_query varchar,
            page integer,
            results_per_page integer,
            max_days_old integer,
            count_reported integer,
            source_id varchar,
            title varchar,
            description varchar,
            posted_at timestamp,
            company_name varchar,
            salary_min double,
            salary_max double,
            salary_is_predicted varchar,
            contract_type varchar,
            contract_time varchar,
            location_display_name varchar,
            location_region varchar,
            location_city varchar,
            location_area_json varchar,
            latitude double,
            longitude double,
            category_tag varchar,
            category_label varchar,
            redirect_url varchar,
            vacancy_json varchar
        )
        """
    )
    dates_sql = ", ".join(f"'{day}'" for day in run_dates)
    conn.execute(f"delete from raw.adzuna_results where run_date in ({dates_sql})")
    conn.execute(
        f"""
        insert into raw.adzuna_results
        select
            source_file,
            run_date::date,
            try_cast(extracted_at as timestamp),
            country,
            role_query,
            page,
            results_per_page,
            max_days_old,
            count_reported,
            source_id,
            title,
            description,
            try_cast(posted_at as timestamp),
            company_name,
            salary_min,
            salary_max,
            salary_is_predicted,
            contract_type,
            contract_time,
            location_display_name,
            location_region,
            location_city,
            location_area_json,
            latitude,
            longitude,
            category_tag,
            category_label,
            redirect_url,
            vacancy_json
        from read_json_auto('{jsonl_path.as_posix()}', format='newline_delimited')
        """
    )
    total = conn.execute("select count(*) from raw.adzuna_results").fetchone()[0]
    conn.close()
    print(f"DuckDB: {DUCKDB_PATH}")
    print(f"В raw.adzuna_results теперь {total} строк (все даты).")


def load_bigquery(jsonl_path: Path, run_dates: list[str]) -> list[Path]:
    try:
        from google.cloud import bigquery
    except ImportError:
        raise SystemExit(
            "Для BigQuery нужен пакет google-cloud-bigquery.\n"
            "pip install google-cloud-bigquery dbt-bigquery"
        )

    project = gcp_project()
    if not project:
        raise SystemExit(
            "Не задан GCP_PROJECT. Добавьте его в .env или в окружение."
        )

    client = bigquery.Client(project=project, location=gcp_location())
    dataset_ref = bigquery.Dataset(f"{project}.{BQ_RAW_DATASET}")
    dataset_ref.location = gcp_location()
    client.create_dataset(dataset_ref, exists_ok=True)

    table_id = f"{project}.{BQ_RAW_DATASET}.{BQ_RAW_TABLE}"
    schema = [
        bigquery.SchemaField("source_file", "STRING"),
        bigquery.SchemaField("run_date", "DATE"),
        bigquery.SchemaField("extracted_at", "TIMESTAMP"),
        bigquery.SchemaField("country", "STRING"),
        bigquery.SchemaField("role_query", "STRING"),
        bigquery.SchemaField("page", "INT64"),
        bigquery.SchemaField("results_per_page", "INT64"),
        bigquery.SchemaField("max_days_old", "INT64"),
        bigquery.SchemaField("count_reported", "INT64"),
        bigquery.SchemaField("source_id", "STRING"),
        bigquery.SchemaField("title", "STRING"),
        bigquery.SchemaField("description", "STRING"),
        bigquery.SchemaField("posted_at", "TIMESTAMP"),
        bigquery.SchemaField("company_name", "STRING"),
        bigquery.SchemaField("salary_min", "FLOAT64"),
        bigquery.SchemaField("salary_max", "FLOAT64"),
        bigquery.SchemaField("salary_is_predicted", "STRING"),
        bigquery.SchemaField("contract_type", "STRING"),
        bigquery.SchemaField("contract_time", "STRING"),
        bigquery.SchemaField("location_display_name", "STRING"),
        bigquery.SchemaField("location_region", "STRING"),
        bigquery.SchemaField("location_city", "STRING"),
        bigquery.SchemaField("location_area_json", "STRING"),
        bigquery.SchemaField("latitude", "FLOAT64"),
        bigquery.SchemaField("longitude", "FLOAT64"),
        bigquery.SchemaField("category_tag", "STRING"),
        bigquery.SchemaField("category_label", "STRING"),
        bigquery.SchemaField("redirect_url", "STRING"),
        bigquery.SchemaField("vacancy_json", "STRING"),
    ]
    table = bigquery.Table(table_id, schema=schema)
    table.time_partitioning = bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.DAY,
        field="run_date",
    )
    # DELETE в BigQuery — DML, без billing его нет. Партиция + WRITE_TRUNCATE
    # заменяет день целиком load-джобой, это не DML.
    try:
        existing = client.get_table(table_id)
        partitioned = bool(existing.time_partitioning)
    except Exception:
        partitioned = False
        existing = None
    if existing is not None and not partitioned:
        client.delete_table(table_id)
        existing = None
    if existing is None:
        client.create_table(table)

    parts: list[Path] = []
    by_date: dict[str, list[str]] = {day: [] for day in run_dates}
    with jsonl_path.open(encoding="utf-8") as handle:
        for line in handle:
            day = json.loads(line)["run_date"]
            by_date.setdefault(day, []).append(line)

    job_config = bigquery.LoadJobConfig(
        schema=schema,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        time_partitioning=bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="run_date",
        ),
    )
    for day, lines in by_date.items():
        if not lines:
            continue
        part_path = jsonl_path.with_name(f"adzuna_results_{day}.jsonl")
        part_path.write_text("".join(lines), encoding="utf-8")
        parts.append(part_path)
        partition_id = f"{table_id}${day.replace('-', '')}"
        with part_path.open("rb") as handle:
            job = client.load_table_from_file(
                handle, partition_id, job_config=job_config
            )
        job.result()
        print(f"  партиция {day}: {len(lines)} строк")
    print(f"BigQuery: {table_id}, даты {', '.join(run_dates)}")
    return parts


def main() -> int:
    args = parse_args()
    rows, files = collect_rows(args.run_date)

    run_dates: list[str] = []
    skipped: list[str] = []
    for day in sorted({row["run_date"] for row in rows}):
        problems, source = raw_status.day_problems(day)
        if problems and not args.allow_incomplete:
            skipped.append(day)
            print(f"{day}: день неполный ({source}), не загружаю:")
            for problem in problems[:10]:
                print(f"  {problem}")
            if len(problems) > 10:
                print(f"  и ещё {len(problems) - 10}")
            continue
        if problems:
            print(f"{day}: день неполный, загружаю по --allow-incomplete")
        run_dates.append(day)

    if not run_dates:
        print("Загружать нечего: полных дней нет.")
        return 1
    rows = [row for row in rows if row["run_date"] in run_dates]
    unique_ids = {row["source_id"] for row in rows if row["source_id"]}

    jsonl_path = WAREHOUSE_DIR / "adzuna_results.jsonl"
    write_jsonl(rows, jsonl_path)

    print(
        f"Файлов: {len(files)}, записей: {len(rows)}, "
        f"уникальных id: {len(unique_ids)}, даты: {', '.join(run_dates)}"
    )
    print(f"Промежуточный jsonl: {jsonl_path}")

    temp_files = [jsonl_path]
    if args.backend == "duckdb":
        load_duckdb(jsonl_path, run_dates)
    else:
        temp_files += load_bigquery(jsonl_path, run_dates)

    # Промежуточные jsonl — копия сырья в другом формате, и весят они столько же.
    # После успешной загрузки они не нужны: склад уже содержит эти строки,
    # а пересобрать их можно из data/raw за минуту.
    if not args.keep_temp:
        freed = sum(path.stat().st_size for path in temp_files if path.exists())
        for path in temp_files:
            path.unlink(missing_ok=True)
        print(f"Промежуточные файлы убраны, освобождено {freed / 1e6:.1f} МБ "
              f"(оставить: --keep-temp).")
    return 1 if skipped else 0


if __name__ == "__main__":
    sys.exit(main())
