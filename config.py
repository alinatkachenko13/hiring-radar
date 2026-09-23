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
MAX_DAYS_OLD = 2        # окно свежести по умолчанию: пропуск запуска компенсируется следующим
MAX_PAGES = 400         # предохранитель от бесконечной пагинации, не рабочий лимит

# Потолок выдачи Adzuna: 100 страниц по 50. Глубже API не отдаёт ошибку,
# а молча повторяет сотую страницу, поэтому обрезку видно только по
# повторяющимся id (NOTES, GAP 7).
RESULT_CAP = 100 * RESULTS_PER_PAGE

# Режим сбора выбирается по паре и упирается в тот же потолок.
#
# Без окна (весь запас) собираются пары, чей запас меньше потолка. Только такой
# сбор даёт срок жизни объявления: вакансия пропадает из выдачи, когда её сняли,
# а не когда ей исполнилось трое суток.
#
# С окном собираются пары, чей запас в потолок не помещается. По ним считается
# только поток новых вакансий.
STOCK_COUNTRIES = ["nl", "pl", "de", "ca"]
STOCK_PAIRS = {
    ("gb", "analytics engineer"),
    ("gb", "data analyst"),
    ("gb", "ml engineer"),
}
# Пары, где даже поток за двое суток не влезает в потолок: окно сужается.
# Цена — страховка: пропущенный запуск такая пара теряет безвозвратно.
WINDOW_OVERRIDES = {("us", "data engineer"): 1}

SLEEP_SEC = 0.25        # 300 запросов в минуту = 1 запрос в 0.2 с, берём с запасом
TIMEOUT_SEC = 30
RETRIES = 3             # на сетевые ошибки, 5xx и 429
RETRY_BACKOFF_SEC = [5, 30, 120]    # паузы между попытками: сбой источника
                                    # длится минуты, а не секунды (NOTES, 23.09)
RESUME = True           # пропускать пары, уже собранные сегодня до конца
RAW_COMPRESS_AFTER_DAYS = 14    # старше этого сырьё лежит сжатым (compress_raw.py):
                                # перепись даёт ~50 МБ в день, gzip жмёт их в ~10 раз


def window_for(country: str, role: str) -> int | None:
    """Окно свежести пары в днях. None — окна нет, собирается весь запас."""
    if country in STOCK_COUNTRIES or (country, role) in STOCK_PAIRS:
        return None
    return WINDOW_OVERRIDES.get((country, role), MAX_DAYS_OLD)


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
