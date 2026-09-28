"""Защита ключей в логах и лесенка повторов."""
from __future__ import annotations

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
