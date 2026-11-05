"""Защита ключей в логах и лесенка повторов."""
from __future__ import annotations

import json

import pytest

import extract


def test_mask_removes_keys_from_any_text():
    """requests кладёт полный адрес внутрь текста исключения, а логи хранятся."""
    text = ("HTTPError for url: https://api.adzuna.com/v1/api/jobs/gb/search/1"
            "?app_id=test-app-id&app_key=test-app-key&results_per_page=50")

    masked = extract.mask(text)

    assert "test-app-key" not in masked
    assert "test-app-id" not in masked
    assert masked.endswith("app_id=***&app_key=***&results_per_page=50")


@pytest.mark.parametrize("attempt, pause", [(1, 5), (2, 30), (3, 120), (4, 120)])
def test_backoff_survives_a_few_minutes_of_source_failure(attempt, pause):
    """Секундные паузы сожгли три попытки за шесть секунд (NOTES, 23.09)."""
    assert extract.backoff(attempt) == pause


class FakeAdzuna:
    """Выдача Adzuna по окнам: сколько вакансий в пару при каждом окне.

    Ведёт себя как настоящая: потолок в 100 страниц, за ним повторяется сотая.
    """

    def __init__(self, totals: dict):
        self.totals = totals
        self.calls: list[tuple] = []

    def __call__(self, country, role, page, window):
        self.calls.append((page, window))
        total = self.totals[window]
        reachable = min(total, 5000)
        start = min((page - 1) * 50, max(reachable - 50, 0))
        results = [{"id": str(number)} for number in range(start, min(start + 50, reachable))]
        return {"payload": {"results": results, "count": total}, "headers": {}, "url": "x"}


@pytest.fixture
def fake_api(raw_dir, monkeypatch):
    """Подменяет сеть и путь сырья в extract, возвращает установщик выдачи."""
    monkeypatch.setattr(extract, "RAW_DIR", raw_dir)
    monkeypatch.setattr(extract, "RUN_DATE", "2026-11-05")
    monkeypatch.setattr(extract.time, "sleep", lambda _: None)

    def install(totals: dict) -> FakeAdzuna:
        api = FakeAdzuna(totals)
        monkeypatch.setattr(extract, "fetch_page", api)
        return api
    return install


def test_stock_that_fits_stays_a_stock(fake_api):
    fake_api({None: 120})

    result = extract.collect_pair("nl", "data engineer")

    assert result.state == "complete"
    assert (result.window, result.demoted, result.unfittable) == (None, False, False)
    assert result.collected == 120


def test_stock_over_the_cap_steps_down_after_the_first_page(fake_api):
    """ca / data engineer: 6 322 при потолке 5 000. Ста запросов на заведомую обрезку нет."""
    api = fake_api({None: 6322, 2: 900})

    result = extract.collect_pair("nl", "data engineer")

    assert result.state == "complete"
    assert (result.window, result.demoted, result.unfittable) == (2, True, False)
    assert [call for call in api.calls if call[1] is None] == [(1, None)]


def test_steps_down_again_when_the_window_does_not_fit_either(fake_api):
    """us / analytics engineer на 2 дня: 5 196–5 740 при потолке 5 000 (02–07.10)."""
    fake_api({None: 6000, 2: 5400, 1: 3000})

    result = extract.collect_pair("nl", "data engineer")

    assert result.window == 1
    assert result.state == "complete"
    assert result.demoted


def test_pair_that_does_not_fit_even_in_one_day_is_unfittable(fake_api):
    """us / data engineer: 5 000–18 663 за сутки. Выдача берётся, сколько даёт API."""
    fake_api({1: 9000})

    result = extract.collect_pair("us", "data engineer")

    assert result.state == "truncated"
    assert (result.window, result.unfittable) == (1, True)
    assert result.collected == 5000


def test_pages_of_the_abandoned_window_do_not_stay_in_the_raw_layer(fake_api, raw_dir):
    """Сырьё пары должно быть одного окна, иначе dbt перепутает режимы."""
    fake_api({None: 6322, 2: 100})

    extract.collect_pair("nl", "data engineer")

    windows = {json.loads(path.read_text())["_meta"]["max_days_old"]
               for path in raw_dir.glob("raw_*.json")}
    assert windows == {2}


def test_truncation_mid_collection_also_steps_down(fake_api, monkeypatch):
    """Выдача под порогом, но обрезалась: 4 697, собрано 2 183 (ca, 09.10)."""
    api = fake_api({None: 4400, 2: 300})

    def reshuffled(country, role, page, window):
        fetched = FakeAdzuna.__call__(api, country, role, page, window)
        if window is None and page > 3:     # выдача пошла по кругу
            fetched["payload"]["results"] = [{"id": str(n)} for n in range(100, 150)]
        return fetched

    monkeypatch.setattr(extract, "fetch_page", reshuffled)

    result = extract.collect_pair("nl", "data engineer")

    assert (result.state, result.window, result.demoted) == ("complete", 2, True)
