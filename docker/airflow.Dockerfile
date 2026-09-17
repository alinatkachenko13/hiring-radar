FROM apache/airflow:3.3.1-python3.12

# Пайплайн работает в отдельном окружении: зависимости dbt и google-cloud
# не смешиваются с зависимостями самого Airflow.
COPY requirements.txt /tmp/requirements.txt
RUN python -m venv /home/airflow/pipeline-venv \
 && /home/airflow/pipeline-venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt
