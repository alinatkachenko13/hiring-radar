#!/bin/bash
# Сборка витрин в BigQuery. Ключ: gcp-service-account.json в корне репо.
set -euo pipefail
cd "$(dirname "$0")"
source .venv/bin/activate
export GCP_PROJECT="${GCP_PROJECT:-$(python -c 'from config import gcp_project; print(gcp_project() or "")')}"
export GCP_LOCATION="${GCP_LOCATION:-$(python -c 'from config import gcp_location; print(gcp_location())')}"
export GOOGLE_APPLICATION_CREDENTIALS="${GOOGLE_APPLICATION_CREDENTIALS:-$(python -c 'from config import gcp_keyfile; p=gcp_keyfile(); print(p or "")')}"
if [ -z "$GCP_PROJECT" ] || [ -z "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
  echo "Нужны GCP_PROJECT и файл gcp-service-account.json (см. .env.example)."
  exit 1
fi
cd dbt
exec dbt build --profiles-dir . --target prod
