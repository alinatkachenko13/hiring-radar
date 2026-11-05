"""Сообщение в Telegram тому, кто отвечает за пайплайн.

Планировщик вызывает send_telegram, когда шаг упал после всех повторов.

Проверить настройку:   python notify.py "проверка"
Узнать свой chat_id:   python notify.py --chat-id
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

from config import PROJECT_DIR, telegram_settings


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


def find_chat_id() -> int:
    """Показывает chat_id тех, кто уже писал боту, и дописывает его в .env.

    Telegram не даёт узнать адресата заранее: сначала человек пишет боту,
    и только потом бот видит чат. Поэтому перед запуском надо отправить
    боту любое сообщение, хотя бы /start.
    """
    token, chat_id = telegram_settings()
    if not token:
        print("Нет TELEGRAM_BOT_TOKEN. Получите токен у @BotFather и впишите в .env.")
        return 1

    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            updates = json.load(response).get("result", [])
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        print(f"Telegram недоступен: {str(error).replace(token, '***')}")
        return 1

    chats = {}
    for update in updates:
        chat = (update.get("message") or update.get("channel_post") or {}).get("chat")
        if chat:
            name = chat.get("username") or chat.get("title") or chat.get("first_name")
            chats[chat["id"]] = name

    if not chats:
        print("Боту никто не писал. Откройте чат с ним в Telegram и отправьте /start,\n"
              "потом запустите эту команду снова.")
        return 1

    for found, name in chats.items():
        print(f"chat_id: {found}   ({name})")

    if chat_id:
        print(f"В .env уже записан TELEGRAM_CHAT_ID={chat_id}, не трогаю.")
        return 0

    env_path = PROJECT_DIR / ".env"
    only = next(iter(chats))
    if len(chats) == 1 and env_path.exists():
        with env_path.open("a", encoding="utf-8") as handle:
            handle.write(f"\nTELEGRAM_CHAT_ID={only}\n")
        print(f"Записала TELEGRAM_CHAT_ID={only} в .env.")
    return 0


if __name__ == "__main__":
    if "--chat-id" in sys.argv:
        sys.exit(find_chat_id())
    message = " ".join(sys.argv[1:]) or "hiring-radar: проверка уведомлений"
    sys.exit(0 if send_telegram(message) else 1)
