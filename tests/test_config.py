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


def test_canada_data_engineer_is_a_flow_pair():
    """Запас перерос потолок 11.10.2026 и держал день взаперти 26 суток."""
    assert config.window_for("ca", "data engineer") == config.MAX_DAYS_OLD


def test_other_canadian_roles_still_fit_the_stock():
    for role in ("analytics engineer", "data analyst", "data scientist", "ml engineer"):
        assert config.window_for("ca", role) is None


def test_ladder_steps_down_from_stock_to_one_day():
    assert config.window_ladder("nl", "data engineer") == [None, config.MAX_DAYS_OLD, 1]


def test_ladder_of_a_flow_pair_has_only_the_narrower_window():
    assert config.window_ladder("gb", "data engineer") == [config.MAX_DAYS_OLD, 1]


def test_ladder_of_the_narrowest_pair_is_a_single_step():
    """Дальше некуда: обрезка здесь означает, что пара не влезает вовсе."""
    assert config.window_ladder("us", "data engineer") == [1]


def test_pair_steps_down_before_the_cap_not_at_it():
    """Выдача 4 697 из 5 000 уже обрезалась (ca, 09.10), поэтому запас — 90%."""
    assert config.over_fallback_share(4697)
    assert not config.over_fallback_share(4500)


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
