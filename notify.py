"""Сообщение в Telegram тому, кто отвечает за пайплайн.

Планировщик вызывает send_telegram, когда шаг упал после всех повторов.
Проверить настройку вручную:  python notify.py "проверка"
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

from config import telegram_settings


def send_telegram(text: str) -> bool:
    """Отправляет сообщение. Никогда не падает: алерт не должен ломать сам пайплайн."""
    token, chat_id = telegram_settings()
    if not token or not chat_id:
        print("Telegram не настроен: нужны TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    try:
        with urllib.request.urlopen(url, data=data, timeout=15) as response:
            ok = bool(json.load(response).get("ok"))
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        # Токен входит в адрес запроса и может оказаться в тексте ошибки.
        print(f"Telegram: сообщение не отправлено, {str(error).replace(token, '***')}")
        return False

    print("Telegram: отправлено" if ok else "Telegram: API ответил ok=false")
    return ok


if __name__ == "__main__":
    message = " ".join(sys.argv[1:]) or "hiring-radar: проверка уведомлений"
    sys.exit(0 if send_telegram(message) else 1)
