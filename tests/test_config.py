"""Режим сбора пары и чтение .env."""
from __future__ import annotations

import pytest

import config


@pytest.mark.parametrize("country, role", [
    ("nl", "data engineer"),        # страна целиком собирается запасом
    ("pl", "ml engineer"),
    ("gb", "analytics engineer"),   # отдельная пара из STOCK_PAIRS
])
def test_stock_pairs_collected_without_window(country, role):
    """Запас собирается без окна: только так виден срок жизни вакансии."""
    assert config.window_for(country, role) is None


def test_window_override_narrows_the_day():
    """Пара, которая не влезает в потолок за двое суток, сужается до одних."""
    assert config.window_for("us", "data engineer") == 1


def test_default_window_is_two_days():
    """Остальные пары собираются потоком: пропуск запуска догоняется следующим."""
    assert config.window_for("gb", "data engineer") == config.MAX_DAYS_OLD


def test_partial_pair_is_declared_only_where_expected():
    assert config.is_partial_pair("us", "data engineer")
    assert not config.is_partial_pair("gb", "data engineer")


def test_role_slug_fits_a_file_name():
    assert config.role_slug("analytics engineer") == "analytics-engineer"


def test_dotenv_ignores_comments_and_strips_quotes(tmp_path):
    path = tmp_path / ".env"
    path.write_text(
        "# комментарий\n"
        "\n"
        "ADZUNA_APP_ID=plain\n"
        'ADZUNA_APP_KEY="in-quotes"\n'
        "TELEGRAM_BOT_TOKEN = 12345:AA-BB \n"
        "мусор без равенства\n",
        encoding="utf-8",
    )
    assert config._read_dotenv(path) == {
        "ADZUNA_APP_ID": "plain",
        "ADZUNA_APP_KEY": "in-quotes",
        "TELEGRAM_BOT_TOKEN": "12345:AA-BB",
    }


def test_dotenv_keeps_equals_inside_value(tmp_path):
    """Ключи с '=' внутри — строка режется по первому знаку, не по каждому."""
    path = tmp_path / ".env"
    path.write_text("KEY=abc=def==\n", encoding="utf-8")
    assert config._read_dotenv(path) == {"KEY": "abc=def=="}


def test_dotenv_missing_file_is_not_an_error(tmp_path):
    assert config._read_dotenv(tmp_path / "нет-такого") == {}
