"""Продовый сбор вакансий из Adzuna: все страны × все роли, с пагинацией.

Принцип: сырьё сохраняется как пришло, без разбора на колонки. Один файл на
один запрос (страна, роль, страница). Всё, что нужно знать о происхождении
данных, лежит рядом в блоке _meta — не надо восстанавливать по имени файла.

Итог каждой пары пишется в data/raw/status_<дата>.json: complete, failed или
truncated (см. raw_status.py). Повторный запуск дособирает только неполные пары,
а load.py грузит день, только когда все пары complete.

Запуск:  python extract.py
         RUN_DATE=2026-09-17 python extract.py   (так дату передаёт планировщик)
"""
import json
import os
import sys
import time
from datetime import date, datetime, timezone
from typing import NamedTuple

import requests

import raw_status
from config import (
    BASE_URL,
    COUNTRIES,
    MAX_PAGES,
    RAW_DIR,
    RESULT_CAP,
    RESULTS_PER_PAGE,
    RESUME,
    RETRIES,
    RETRY_BACKOFF_SEC,
    ROLES,
    SLEEP_SEC,
    TIMEOUT_SEC,
    credentials,
    is_partial_pair,
    over_fallback_share,
    role_slug,
    window_for,
    window_ladder,
)

APP_ID, APP_KEY = credentials()
# Планировщик передаёт дату явно: повтор после полуночи должен дособрать тот же день.
RUN_DATE = os.environ.get("RUN_DATE") or date.today().isoformat()


def mask(text: str) -> str:
    """Убирает ключи из любого текста перед выводом.

    Нужно не только для URL, который мы формируем сами: requests вкладывает
    полный адрес запроса внутрь текста исключения, и без маскировки app_key
    уезжает в лог целиком. В Airflow эти логи хранятся.
    """
    return str(text).replace(APP_KEY, "***").replace(APP_ID, "***")


def backoff(attempt: int) -> float:
    """Пауза перед повтором: 5, 30, 120 секунд.

    Коротких пауз мало. 23.09 Adzuna отдавал 503 около трёх минут, и три попытки
    подряд с паузами в секунды сожгли их за шесть секунд: семь пар упали разом.
    Эта лесенка переживает сбой источника на пару минут без внешнего повтора.
    """
    return RETRY_BACKOFF_SEC[min(attempt, len(RETRY_BACKOFF_SEC)) - 1]


def fetch_page(country: str, role: str, page: int, window: int | None) -> dict | None:
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
    }
    # Окна может не быть: тогда запрашивается весь запас по паре.
    if window is not None:
        params["max_days_old"] = window

    for attempt in range(1, RETRIES + 1):
        last_attempt = attempt == RETRIES
        try:
            response = requests.get(url, params=params, timeout=TIMEOUT_SEC)
        except requests.RequestException as error:
            print(f"    сеть: {mask(repr(error))}, попытка {attempt} из {RETRIES}")
            if not last_attempt:
                time.sleep(backoff(attempt))
            continue

        if response.status_code == 200:
            return {
                "payload": response.json(),
                "headers": dict(response.headers),
                "url": mask(response.url),
            }

        # 5xx: сбой на стороне API. 429: «слишком часто, повторите позже».
        # Оба временные, поэтому повторяются с паузой; для 429 учитываем Retry-After.
        if response.status_code >= 500 or response.status_code == 429:
            wait = backoff(attempt)
            retry_after = response.headers.get("Retry-After", "")
            if retry_after.isdigit():
                wait = max(wait, int(retry_after))
            print(f"    {response.status_code} от API, попытка {attempt} из {RETRIES}")
            if not last_attempt:
                time.sleep(wait)
            continue

        # Остальные 4xx повторять бессмысленно: это ошибка в самом запросе.
        print(f"    ошибка {response.status_code}: {mask(response.text[:200])}")
        return None

    print("    не удалось получить страницу после всех попыток")
    return None


def save(
    country: str, role: str, page: int, fetched: dict, found: int, window: int | None
) -> None:
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
            # null означает сбор всего запаса, без окна свежести
            "max_days_old": window,
            "count_reported": found,
            "request_url": fetched["url"],
            "response_headers": fetched["headers"],
        },
        "payload": fetched["payload"],
    }
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8"
    )


class PairResult(NamedTuple):
    """Итог сбора одной пары. Поля названы как аргументы raw_status.record_pair."""
    state: str            # raw_status.COMPLETE, FAILED или TRUNCATED
    collected: int        # разных вакансий
    pages: int            # сохранённых страниц
    count_reported: int   # count из ответа Adzuna
    window: int | None = None   # окно, которым собрана пара; None — весь запас
    demoted: bool = False       # пара спустилась с предпочтительного окна
    unfittable: bool = False    # обрезана на самой узкой ступени: не влезает вовсе


def collect(
    country: str, role: str, window: int | None, can_narrow: bool = False
) -> PairResult:
    """Забирает все страницы пары одним окном.

    Считаются разные вакансии, а не строки. Разница принципиальна: за сотой
    страницей Adzuna повторяет одну и ту же выдачу, и счётчик строк доводил
    обрезанную пару до состояния «собрана полностью» (NOTES, GAP 7).

    can_narrow — есть ли ступень уже этой. Тогда выдача, не влезающая в потолок,
    бросается сразу после первой страницы: ещё девяносто девять запросов
    дали бы тот же результат, обрезку.
    """
    seen: set[str] = set()
    pages = 0
    found = 0

    for page in range(1, MAX_PAGES + 1):
        fetched = fetch_page(country, role, page, window)
        time.sleep(SLEEP_SEC)

        if fetched is None:
            return PairResult(raw_status.FAILED, len(seen), pages, found)

        payload = fetched["payload"]
        results = payload.get("results") or []
        found = payload.get("count", 0)

        save(country, role, page, fetched, found, window)
        pages += 1
        new = {item["id"] for item in results if item.get("id")} - seen
        seen |= new

        if page == 1 and over_fallback_share(found):
            print(f"    ВНИМАНИЕ: выдача {found} близка к потолку {RESULT_CAP}")
            if can_narrow:
                return PairResult(raw_status.TRUNCATED, len(seen), pages, found)

        print(
            f"    стр. {page}: получено {len(results)}, новых {len(new)}, "
            f"всего {len(seen)} из {found}"
        )

        # Страница без единой новой вакансии означает, что выдача пошла по кругу.
        if results and not new:
            print(f"    выдача повторяется: упёрлись в потолок {RESULT_CAP}, пара обрезана")
            return PairResult(raw_status.TRUNCATED, len(seen), pages, found)

        # Последняя страница: неполная выдача или набрали всё, что обещал count.
        if len(results) < RESULTS_PER_PAGE or len(seen) >= found:
            return PairResult(raw_status.COMPLETE, len(seen), pages, found)

    # Выдача не кончилась к пределу страниц: данные обрезаны, это не успех.
    print(f"    упёрлись в предел MAX_PAGES={MAX_PAGES}, пара обрезана")
    return PairResult(raw_status.TRUNCATED, len(seen), pages, found)


def describe(window: int | None) -> str:
    return "весь запас" if window is None else f"окно {window} дн."


def collect_pair(country: str, role: str) -> PairResult:
    """Собирает пару, спускаясь по лестнице окон, пока выдача не влезет в потолок.

    Пара, у которой запас перерос потолок, не должна навсегда блокировать день
    (так 11.10.2026 встала ca / data engineer). Обрезка на самой узкой ступени —
    это пара, которая не влезает вовсе: такая день не блокирует.
    """
    ladder = window_ladder(country, role)
    for step, window in enumerate(ladder):
        last = step == len(ladder) - 1
        if step:
            print(f"    переход: {describe(window)}")
        result = collect(country, role, window, can_narrow=not last)
        if result.state != raw_status.TRUNCATED or last:
            return result._replace(
                window=window,
                demoted=step > 0,
                unfittable=result.state == raw_status.TRUNCATED,
            )
        # Страницы обрезанного окна не нужны: сырьё пары должно быть одного окна.
        for path in raw_status.pair_files(RUN_DATE, country, role):
            path.unlink()
    raise AssertionError("лестница окон не бывает пустой")


def main() -> int:
    pairs = [(country, role) for country in COUNTRIES for role in ROLES]
    stock = sum(1 for country, role in pairs if window_for(country, role) is None)
    print(f"Сбор за {RUN_DATE}: {len(COUNTRIES)} стран × {len(ROLES)} ролей.\n"
          f"Весь запас: {stock} пар, поток с окном: {len(pairs) - stock}.\n"
          f"Сырьё: {RAW_DIR}\n")
    raw_status.start_day(RUN_DATE, pairs)

    total_vacancies = 0
    total_pages = 0
    skipped = 0
    incomplete: list[tuple[str, str, str]] = []
    unfittable: set[tuple[str, str]] = set()
    demoted: list[str] = []

    for country, role in pairs:
        files = raw_status.pair_files(RUN_DATE, country, role)
        if RESUME and files:
            state = raw_status.pair_state(RUN_DATE, country, role)
            if state is None and raw_status.complete_by_files(RUN_DATE, country, role):
                # Пара собрана запуском без файла статусов: фиксируем по файлам.
                raw_status.record_pair(
                    RUN_DATE, country, role, raw_status.COMPLETE, pages=len(files)
                )
                state = raw_status.COMPLETE
            if state == raw_status.COMPLETE:
                skipped += 1
                continue

        # Недособранная пара пересобирается целиком, а не дописывается.
        # Выдача за время между запусками сдвигается, поэтому склейка
        # старых страниц с новыми дала бы и пропуски, и повторы.
        if files:
            print(f"{country} / {role}: было {len(files)} стр., пересобираю")
            for path in files:
                path.unlink()
        else:
            print(f"{country} / {role} ({describe(window_for(country, role))})")

        result = collect_pair(country, role)
        raw_status.record_pair(
            RUN_DATE, country, role, result.state,
            pages=result.pages, collected=result.collected,
            count_reported=result.count_reported,
            window=result.window, demoted=result.demoted, unfittable=result.unfittable,
        )
        total_vacancies += result.collected
        total_pages += result.pages
        if result.state != raw_status.COMPLETE:
            incomplete.append((country, role, result.state))
        if result.unfittable:
            unfittable.add((country, role))
        if result.demoted:
            demoted.append(f"{country} / {role}: {describe(result.window)}")

    print(f"\nЗа этот запуск: {total_vacancies} записей в {total_pages} файлах.")
    if skipped:
        print(f"Пропущено готовых пар: {skipped}. Чтобы пересобрать день заново, "
              "удалите за эту дату файлы raw_* и status_* в data/raw.")
    print("Дубли между ролями ожидаемы и снимаются дедупликацией по id в staging.")

    if demoted:
        print("\nСпустились по лестнице окон (запас не влез в потолок выдачи):")
        for line in demoted:
            print(f"  {line}")

    def expected(country: str, role: str, state: str) -> bool:
        """Обрезка пары, которая не влезает в потолок даже на самой узкой ступени."""
        return state == raw_status.TRUNCATED and (
            (country, role) in unfittable or is_partial_pair(country, role)
        )

    if incomplete:
        print("\nНе собраны полностью:")
        for country, role, state in incomplete:
            note = ""
            if expected(country, role, state):
                note = " — обрезка ожидаема, день не блокируется"
            print(f"  {country} / {role}: {state}{note}")

    blocking = [
        (country, role, state)
        for country, role, state in incomplete
        if not expected(country, role, state)
    ]
    if blocking:
        print("Повторный запуск дособерёт только их. "
              "Пока хоть одна пара не complete, load.py этот день не загрузит.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
