# hiring-radar

[![CI](https://github.com/alinatkachenko13/hiring-radar/actions/workflows/ci.yml/badge.svg)](https://github.com/alinatkachenko13/hiring-radar/actions/workflows/ci.yml)

A daily pipeline that collects data job vacancies (6 countries, 5 roles), keeps their history in a warehouse and shows how the market changes day to day. Job boards show today's snapshot; the value here is the accumulated history.

## Architecture

```mermaid
flowchart LR
    viewer(["`**Viewer**
[Person]
Explores the data job market`"])

    subgraph system["hiring-radar"]
        dashboard["`**Dashboard**
[Container: Looker Studio]
Market, salary and company screens`"]
        scheduler["`**Scheduler**
[Container: Airflow]
Runs the pipeline every day`"]
        alerting["`**Alerting**
[Container: Telegram bot]
Turns failures into messages`"]
        collector["`**Collector job**
[Container: Python]
Collects vacancy pages per country and role`"]
        loader["`**Loader job**
[Container: Python]
Loads a complete day`"]
        transformations["`**Transformations**
[Container: dbt]
Models and data tests`"]
        raw[("`**Raw storage**
[Container: JSON files]
API pages and pair statuses`")]
        warehouse[("`**Warehouse**
[Container: BigQuery]
Raw, staging, intermediate, marts`")]
    end

    adzuna["`**Adzuna API**
[External system]
Source of vacancies`"]
    telegram["`**Telegram**
[External system]
Delivers messages`"]
    maintainer(["`**Maintainer**
[Person]
Gets alerts, fixes the pipeline`"])

    viewer -- "opens [HTTPS]" --> dashboard
    dashboard -- "queries marts [SQL]" --> warehouse
    scheduler -- "starts, retries incomplete pairs" --> collector
    scheduler -- "starts when the day is complete" --> loader
    scheduler -- "runs dbt build" --> transformations
    scheduler -- "sends failure events" --> alerting
    collector -- "requests pages [HTTPS, JSON]" --> adzuna
    collector -- "writes pages and pair statuses" --> raw
    loader -- "reads the day" --> raw
    loader -- "replaces the day's rows [SQL]" --> warehouse
    transformations -- "builds marts, runs tests [SQL]" --> warehouse
    alerting -- "sends messages [Bot API]" --> telegram
    telegram -- "delivers alerts" --> maintainer

    classDef person fill:#08427B,stroke:#052E56,color:#ffffff
    classDef container fill:#1168BD,stroke:#0B4884,color:#ffffff
    classDef external fill:#8A8A8A,stroke:#6B6B6B,color:#ffffff
    class viewer,maintainer person
    class dashboard,scheduler,alerting,collector,loader,transformations,raw,warehouse container
    class adzuna,telegram external
    style system fill:none,stroke:#666666,stroke-dasharray:6 4
```

## One day of data

```mermaid
sequenceDiagram
    autonumber
    participant SCH as Scheduler
    participant AL as Alerting
    participant CJ as Collector job
    participant API as Adzuna API (external)
    participant RS as Raw storage
    participant LJ as Loader job
    participant TR as Transformations
    participant WH as Warehouse
    participant DB as Dashboard
    actor V as Viewer

    SCH->>CJ: start daily collection
    loop each country and role pair, 6 × 5
        CJ->>API: GET /jobs/{country}/search/{page}
        API-->>CJ: pages of vacancies
        Note over CJ,API: retry on network error, 5xx, 429
        CJ->>RS: store raw pages
        CJ->>RS: record pair status<br/>complete, failed or truncated
    end
    CJ-->>SCH: run status, incomplete pairs
    opt some pairs failed or truncated
        SCH->>CJ: retry incomplete pairs, up to 2 times
        CJ-->>SCH: run status
    end
    alt every pair complete
        SCH->>LJ: load the day
        LJ->>RS: read raw pages<br/>and pair statuses
        LJ->>WH: replace the day's rows<br/>safe to repeat
        SCH->>TR: build models, run tests
        TR->>WH: staging, intermediate, marts
        alt all tests passed
            TR-->>SCH: marts updated
        else some tests failed
            TR-->>SCH: failed tests
            SCH->>AL: alert: tests failed
        end
    else still incomplete after retries
        SCH->>AL: alert: day not loaded
    end

    V->>DB: open dashboard
    DB->>WH: query marts
    WH-->>DB: marts data
    DB-->>V: charts with filters
```

## Key decisions

- **Raw data is kept as received.** Every API page is stored with its request metadata; everything downstream is rebuilt from it.
- **A day is loaded only when every country and role pair is fully collected.** A missing country or a failed query can never look like closed vacancies.
- **Two volume measures.** Ads are unique ids; positions are company + title + country. On the first full run, 32.5% of unique ads repeated one position across cities.
- **Salary counts as disclosed only when two fields agree.** The provider's flag alone was wrong for 3 of 5 countries, the salary field alone for the other 2.
- **Role comes from the title, not the search query.** Search matches descriptions too, so irrelevant titles are filtered out before any volume is counted.
- **Two collection modes.** Where the whole stock fits under the API's 5 000-result ceiling, it is collected without a freshness window: only then does a vacancy leaving the feed mean it was taken down rather than aged out. The rest is collected as a flow and carries no lifetime metric.
- **Skills are not modelled.** Descriptions are cut to 500 characters and name a technology in only 13.4% of them.



## Data model

| Model | Content |
|---|---|
| `fct_vacancy_daily` | one ad per observation day: salary, disclosure, new or gone, listing lifetime where it is measurable |
| `dim_vacancy` | ad attributes with change history (SCD Type 2) |
| `dim_company`, `dim_country`, `dim_location`, `dim_role`, `dim_date` | lookups; `dim_role` also filters irrelevant titles |
| `mart_market_daily`, `mart_salary_daily`, `mart_salary_disclosure`, `mart_company_role`, `mart_city_daily` | aggregated market, salary, company and city views |
| `looker_vacancies` | one flat table the Looker Studio dashboard reads |

## Stack

Python, dbt, BigQuery (DuckDB locally), Airflow, Docker Compose, Looker Studio, Telegram Bot API.

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # add ADZUNA_APP_ID and ADZUNA_APP_KEY
python extract.py       # collect raw pages into data/raw
python load.py          # load them into data/warehouse/hiring_radar.duckdb
cd dbt && dbt build --profiles-dir . && cd ..
python report_marts.py  # summary of the marts
```

BigQuery: fill the GCP values in `.env` (see `.env.example`), keep the service account key in `gcp-service-account.json` (ignored by git), then run `python load.py --backend bigquery` and `./bq_build.sh`.

Scheduler: add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` to `.env`, run `docker compose up -d --build` and open Airflow at http://localhost:8080 (on a shared server the port is set by `AIRFLOW_PORT`, see [docs/deploy.md](docs/deploy.md)). The DAG `hiring_radar_daily` collects, loads the complete day and runs `dbt build` every day at 06:00 UTC.

## Status

| Part | State |
|---|---|
| Collection with per-pair statuses, loading of complete days, dbt models and 26 tests | working |
| CI on GitHub Actions: every push loads two fixture days into DuckDB and runs `dbt build` with all tests | working, see [.github/workflows/ci.yml](.github/workflows/ci.yml) |
| BigQuery warehouse and Looker Studio dashboard with 4 screens | working, see [looker/README.md](looker/README.md) |
| Airflow DAG with retries and Telegram alerts, Docker Compose | built, see [airflow/dags](airflow/dags) and [docker-compose.yml](docker-compose.yml) |
| Deployment on a VPS | deployed, the daily run happens on the server, see [docs/deploy.md](docs/deploy.md) |
| Vacancy closure rule | reworked: a removal counts only where the whole stock is collected, see NOTES.md |
| Lifetime metric on real data | waiting for three census days in a row, first removals expected 26.09 |

