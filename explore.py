"""Разведочные запросы к API. В пайплайн не входит — блокнот для проверок руками.

Раньше здесь был check_first_answer.py с ключами в тексте файла.
"""
import requests

from config import BASE_URL, ROLES, credentials

APP_ID, APP_KEY = credentials()


def count_for(country: str, what: str, max_days_old: int | None = None) -> int:
    """Сколько вакансий находит API по запросу. results_per_page=1 — нам нужно только count."""
    params = {
        "app_id": APP_ID,
        "app_key": APP_KEY,
        "results_per_page": 1,
        "what": what,
    }
    if max_days_old is not None:
        params["max_days_old"] = max_days_old

    response = requests.get(f"{BASE_URL}/{country}/search/1", params=params, timeout=30)
    if response.status_code != 200:
        print(f"  {country} / {what}: ошибка {response.status_code}: {response.text[:200]}")
        return 0
    return response.json().get("count", 0)


if __name__ == "__main__":
    print("Запас открытых вакансий и поток за 2 дня, по ролям (gb):")
    for role in ROLES:
        print(f"  {role:<22} всего {count_for('gb', role):>7}   "
              f"свежих {count_for('gb', role, max_days_old=2):>6}")
