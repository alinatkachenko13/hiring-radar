"""Продовый сбор вакансий из Adzuna: все страны × все роли, с пагинацией.

Принцип: сырьё сохраняется как пришло, без разбора на колонки. Один файл на
один запрос (страна, роль, страница). Всё, что нужно знать о происхождении
данных, лежит рядом в блоке _meta — не надо восстанавливать по имени файла.

Запуск:  python extract.py
"""
import json
import sys
import time
from datetime import date, datetime, timezone

import requests

from config import (
    BASE_URL,
    COUNTRIES,
    MAX_DAYS_OLD,
    MAX_PAGES,
    RAW_DIR,
    RESULTS_PER_PAGE,
    RESUME,
    RETRIES,
    ROLES,
    SLEEP_SEC,
    TIMEOUT_SEC,
    credentials,
    role_slug,
)

APP_ID, APP_KEY = credentials()
RUN_DATE = date.today().isoformat()


def mask(text: str) -> str:
    """Убирает ключи из любого текста перед выводом.

    Нужно не только для URL, который мы формируем сами: requests вкладывает
    полный адрес запроса внутрь текста исключения, и без маскировки app_key
    уезжает в лог целиком. В Airflow эти логи хранятся.
    """
    return str(text).replace(APP_KEY, "***").replace(APP_ID, "***")


def fetch_page(country: str, role: str, page: int) -> dict | None:
    """Один запрос к API. Возвращает разобранный ответ или None при ошибке.

    Статус проверяется до .json(): при ошибке API отдаёт HTML, и .json()
    падает с невнятным JSONDecodeError вместо описания проблемы.
    """
    url = f"{BASE_URL}/{country}/search/{page}"
    params = {
        "app_id": APP_ID,
        "app_key": APP_KEY,
        "results_per_page": RESULTS_PER_PAGE,
        "what": role,
        "max_days_old": MAX_DAYS_OLD,
    }

    for attempt in range(1, RETRIES + 1):
        try:
            response = requests.get(url, params=params, timeout=TIMEOUT_SEC)
        except requests.RequestException as error:
            print(f"    сеть: {mask(repr(error))}, попытка {attempt} из {RETRIES}")
            time.sleep(SLEEP_SEC * attempt * 4)
            continue

        if response.status_code == 200:
            return {
                "payload": response.json(),
                "headers": dict(response.headers),
                "url": mask(response.url),
            }

        if response.status_code >= 500:
            print(f"    {response.status_code} от API, попытка {attempt} из {RETRIES}")
            time.sleep(SLEEP_SEC * attempt * 4)
            continue

        # 4xx повторять бессмысленно: это ошибка в запросе, а не сбой.
        print(f"    ошибка {response.status_code}: {mask(response.text[:200])}")
        return None

    print("    не удалось получить страницу после всех попыток")
    return None


def save(country: str, role: str, page: int, fetched: dict, found: int) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"raw_{RUN_DATE}_{country}_{role_slug(role)}_p{page}.json"
    document = {
        "_meta": {
            "source": "adzuna",
            "run_date": RUN_DATE,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "country": country,
            "role_query": role,
            "page": page,
            "results_per_page": RESULTS_PER_PAGE,
            "max_days_old": MAX_DAYS_OLD,
            "count_reported": found,
            "request_url": fetched["url"],
            "response_headers": fetched["headers"],
        },
        "payload": fetched["payload"],
    }
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def pair_files(country: str, role: str) -> list:
    """Файлы этой пары за сегодня, по возрастанию номера страницы."""
    pattern = f"raw_{RUN_DATE}_{country}_{role_slug(role)}_p*.json"
    return sorted(
        RAW_DIR.glob(pattern),
        key=lambda path: int(path.stem.rsplit("_p", 1)[1]),
    )


def pair_is_complete(country: str, role: str) -> bool:
    """Собрана ли пара до конца. Нужно для повторного запуска.

    Признаков конца два, ровно те же, что в collect(): последняя страница
    неполная, либо набрано не меньше, чем обещал count. Проверять только
    неполную страницу нельзя — крупные выдачи заканчиваются полной страницей,
    и такая пара считалась бы недособранной и качалась заново целиком.
    """
    files = pair_files(country, role)
    if not files:
        return False

    last = json.loads(files[-1].read_text(encoding="utf-8"))
    results = last["payload"].get("results") or []
    if len(results) < RESULTS_PER_PAGE:
        return True

    # Все страницы до последней полные, иначе обход бы на них остановился.
    collected = (last["_meta"]["page"] - 1) * RESULTS_PER_PAGE + len(results)
    return collected >= last["_meta"]["count_reported"]


def collect(country: str, role: str) -> tuple[int, int, int]:
    """Забирает все страницы по паре страна-роль. Возвращает (вакансий, страниц, ошибок)."""
    collected = 0
    pages = 0
    errors = 0

    for page in range(1, MAX_PAGES + 1):
        fetched = fetch_page(country, role, page)
        time.sleep(SLEEP_SEC)

        if fetched is None:
            errors += 1
            break

        payload = fetched["payload"]
        results = payload.get("results") or []
        found = payload.get("count", 0)

        save(country, role, page, fetched, found)
        collected += len(results)
        pages += 1

        print(
            f"    стр. {page}: получено {len(results)}, "
            f"накоплено {collected} из {found}"
        )

        # Последняя страница: неполная выдача или набрали всё, что обещал count.
        if len(results) < RESULTS_PER_PAGE or collected >= found:
            break
    else:
        print(f"    внимание: упёрлись в предохранитель MAX_PAGES={MAX_PAGES}")

    return collected, pages, errors


def main() -> int:
    print(f"Сбор за {RUN_DATE}: {len(COUNTRIES)} стран × {len(ROLES)} ролей, "
          f"окно {MAX_DAYS_OLD} дн.\nСырьё: {RAW_DIR}\n")

    total_vacancies = 0
    total_pages = 0
    failed: list[tuple[str, str]] = []
    skipped = 0

    for country in COUNTRIES:
        for role in ROLES:
            if RESUME and pair_is_complete(country, role):
                skipped += 1
                continue

            # Недособранная пара пересобирается целиком, а не дописывается.
            # Выдача за время между запусками сдвигается, поэтому склейка
            # старых страниц с новыми дала бы и пропуски, и повторы.
            stale = pair_files(country, role)
            if stale:
                print(f"{country} / {role}: было {len(stale)} стр., пересобираю")
                for path in stale:
                    path.unlink()
            else:
                print(f"{country} / {role}")

            collected, pages, errors = collect(country, role)
            total_vacancies += collected
            total_pages += pages
            if errors:
                failed.append((country, role))

    print(f"\nЗа этот запуск: {total_vacancies} записей в {total_pages} файлах.")
    if skipped:
        print(f"Пропущено готовых пар: {skipped}. "
              "Чтобы пересобрать день заново, очистите data/raw за эту дату.")
    print("Дубли между ролями ожидаемы и снимаются дедупликацией по id в staging.")

    if failed:
        print("\nНе собраны до конца:")
        for country, role in failed:
            print(f"  {country} / {role}")
        print("Повторный запуск дособерёт только их.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
