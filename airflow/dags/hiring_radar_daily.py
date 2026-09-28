"""Ежедневный прогон hiring-radar: сбор, загрузка полного дня, dbt build с тестами.

Шаги повторяются сами. Если шаг упал после всех повторов, уходит одно сообщение
в Telegram. В конце дня уходит короткая сводка о том, что собралось. Дата прогона фиксируется первым шагом и передаётся дальше через XCom,
чтобы повтор после полуночи работал с тем же днём.

Запускается в docker-compose.yml: код проекта смонтирован в PROJECT_DIR,
пайплайн работает в своём окружении PIPELINE_PYTHON, отдельном от Airflow.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

try:
    from airflow.sdk import DAG
except ImportError:  # Airflow 2
    from airflow import DAG

try:
    from airflow.providers.standard.operators.bash import BashOperator
except ImportError:  # Airflow 2
    from airflow.operators.bash import BashOperator

PROJECT_DIR = os.environ.get("PROJECT_DIR", "/opt/hiring-radar")
PYTHON = os.environ.get("PIPELINE_PYTHON", "python")
LOAD_BACKEND = os.environ.get("LOAD_BACKEND", "bigquery")
DBT_TARGET = os.environ.get("DBT_TARGET", "prod")

sys.path.insert(0, PROJECT_DIR)

RUN_DATE = "{{ ti.xcom_pull(task_ids='run_date') }}"

ALERTS = {
    "run_date": "the run did not start",
    "collect": "day {day} not loaded: collection stayed incomplete after retries, "
               "see data/raw/status_{day}.json",
    "load": "loading day {day} into the warehouse failed",
    "transform": "dbt build failed for day {day}: a model or a data test",
}


def alert_on_failure(context) -> None:
    """Колбэк Airflow: шаг упал окончательно, сообщаем в Telegram."""
    from notify import send_telegram

    ti = context["ti"]
    day = ti.xcom_pull(task_ids="run_date") or "unknown"
    template = ALERTS.get(ti.task_id, "task " + ti.task_id + " failed for day {day}")
    send_telegram("hiring-radar: " + template.format(day=day))


with DAG(
    dag_id="hiring_radar_daily",
    schedule="0 6 * * *",
    start_date=datetime(2026, 9, 1),
    catchup=False,
    max_active_runs=1,
    default_args={"on_failure_callback": alert_on_failure},
    tags=["hiring-radar"],
) as dag:
    run_date = BashOperator(
        task_id="run_date",
        bash_command="date -u +%F",
    )

    collect = BashOperator(
        task_id="collect",
        bash_command=f"cd {PROJECT_DIR} && RUN_DATE={RUN_DATE} {PYTHON} extract.py",
        retries=2,
        retry_delay=timedelta(minutes=10),
    )

    load = BashOperator(
        task_id="load",
        bash_command=f"cd {PROJECT_DIR} && {PYTHON} load.py {RUN_DATE} --backend {LOAD_BACKEND}",
        retries=1,
        retry_delay=timedelta(minutes=5),
    )

    transform = BashOperator(
        task_id="transform",
        bash_command=f"cd {PROJECT_DIR} && {PYTHON} transform.py {DBT_TARGET}",
        retries=1,
        retry_delay=timedelta(minutes=5),
    )

    # Уборка идёт последней и не влияет на данные: сырьё не удаляется, а сжимается.
    # Падение здесь не должно окрашивать прогон в красный, поэтому повторов нет,
    # а алерт общий: не сжалось сегодня — сожмётся завтра.
    compress = BashOperator(
        task_id="compress",
        bash_command=f"cd {PROJECT_DIR} && {PYTHON} compress_raw.py",
        retries=0,
    )

    # Сводка идёт последней и при любом исходе: all_done. Если день не собрался,
    # алерт уже ушёл, а сводка покажет, что именно осталось неполным.
    # Повторов нет и падать ей нечем: скрипт не роняет прогон.
    report = BashOperator(
        task_id="report",
        bash_command=f"cd {PROJECT_DIR} && {PYTHON} daily_report.py {RUN_DATE}",
        retries=0,
        trigger_rule="all_done",
    )

    run_date >> collect >> load >> transform >> compress >> report
