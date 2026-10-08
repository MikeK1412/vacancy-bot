"""Узнать CHAT_ID группы.

1. Добавьте бота в группу.
2. Напишите в группе любое сообщение с упоминанием бота (например /start@имя_бота).
   Без упоминания бот в группе может не видеть сообщений (режим приватности).
3. Запустите: python get_chat_id.py
4. Скопируйте id группы (начинается с -100) в .env как CHAT_ID.
"""
import sys

import config
from tg import TelegramError, call


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    token, _ = config.telegram_settings()
    if not token:
        sys.exit("Нет BOT_TOKEN. Заполните .env (образец: .env.example).")
    try:
        updates = call(token, "getUpdates", timeout=0)
    except TelegramError as e:
        sys.exit(f"Ошибка Telegram: {e}")
    chats = {}
    for u in updates:
        msg = u.get("message") or u.get("channel_post") or u.get("my_chat_member") or {}
        chat = msg.get("chat")
        if chat:
            chats[chat["id"]] = (chat.get("type"), chat.get("title") or chat.get("username") or chat.get("first_name"))
    if not chats:
        print("Бот пока не видел сообщений. Напишите в группе /start@имя_бота и запустите снова.")
        return
    for chat_id, (kind, title) in chats.items():
        print(f"{chat_id}\t{kind}\t{title}")


if __name__ == "__main__":
    main()
