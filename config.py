"""Конфигурация сбора и чтение ключей.

Ключи берутся из переменных окружения. Если их нет, читается файл .env
рядом со скриптом — чтобы не экспортировать переменные вручную при каждом
запуске из PyCharm. Сам .env в git не попадает (см. .gitignore).
"""
import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
RAW_DIR = PROJECT_DIR / "data" / "raw"
WAREHOUSE_DIR = PROJECT_DIR / "data" / "warehouse"
DUCKDB_PATH = WAREHOUSE_DIR / "hiring_radar.duckdb"
BQ_RAW_DATASET = "hiring_radar_raw"
BQ_RAW_TABLE = "adzuna_results"

BASE_URL = "https://api.adzuna.com/v1/api/jobs"

COUNTRIES = ["gb", "de", "nl", "pl", "us", "ca"]
ROLES = [
    "data engineer",
    "analytics engineer",
    "data analyst",
    "data scientist",
    "ml engineer",
]

RESULTS_PER_PAGE = 50   # максимум, который отдаёт Adzuna
MAX_DAYS_OLD = 2        # окно свежести: пропуск запуска компенсируется следующим
MAX_PAGES = 150         # предохранитель от бесконечной пагинации, не рабочий лимит
                        # us / data engineer за 2 дня даёт ~4000 вакансий = 81 стр.
SLEEP_SEC = 0.25        # 300 запросов в минуту = 1 запрос в 0.2 с, берём с запасом
TIMEOUT_SEC = 30
RETRIES = 3             # на сетевые ошибки, 5xx и 429
RESUME = True           # пропускать пары, уже собранные сегодня до конца


def _read_dotenv(path: Path) -> dict:
    if not path.exists():
        return {}
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def credentials() -> tuple[str, str]:
    """Возвращает (app_id, app_key) или падает с внятным сообщением."""
    dotenv = _read_dotenv(PROJECT_DIR / ".env")
    app_id = os.environ.get("ADZUNA_APP_ID") or dotenv.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY") or dotenv.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        raise SystemExit(
            "Не найдены ключи Adzuna.\n"
            "Либо export ADZUNA_APP_ID=... и ADZUNA_APP_KEY=...,\n"
            "либо положите их в файл .env рядом с extract.py (см. .env.example)."
        )
    return app_id, app_key


def role_slug(role: str) -> str:
    return role.replace(" ", "-")


def _dotenv() -> dict:
    return _read_dotenv(PROJECT_DIR / ".env")


def telegram_settings() -> tuple[str | None, str | None]:
    """(токен бота, id чата) для алертов планировщика, из окружения или .env."""
    dotenv = _dotenv()
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or dotenv.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or dotenv.get("TELEGRAM_CHAT_ID")
    return token, chat_id


GCP_KEY_CANDIDATE = PROJECT_DIR / "gcp-service-account.json"


def apply_gcp_env() -> None:
    """Подставляет GCP_* из .env в os.environ, чтобы ими пользовались
    google-cloud и dbt. Ключ: GOOGLE_APPLICATION_CREDENTIALS или файл
    gcp-service-account.json в корне проекта.
    """
    dotenv = _dotenv()
    project = os.environ.get("GCP_PROJECT") or dotenv.get("GCP_PROJECT")
    if project:
        os.environ["GCP_PROJECT"] = project
    os.environ["GCP_LOCATION"] = (
        os.environ.get("GCP_LOCATION") or dotenv.get("GCP_LOCATION") or "EU"
    )
    creds = (
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        or dotenv.get("GOOGLE_APPLICATION_CREDENTIALS")
    )
    path = Path(creds) if creds else GCP_KEY_CANDIDATE
    if not path.is_absolute():
        path = PROJECT_DIR / path
    if path.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(path)


apply_gcp_env()


def gcp_project() -> str | None:
    return os.environ.get("GCP_PROJECT") or _dotenv().get("GCP_PROJECT")


def gcp_location() -> str:
    return os.environ.get("GCP_LOCATION") or _dotenv().get("GCP_LOCATION") or "EU"


def gcp_keyfile() -> Path | None:
    raw = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not raw:
        return None
    path = Path(raw)
    return path if path.exists() else None
