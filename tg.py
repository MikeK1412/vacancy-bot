"""Минимальный клиент Telegram Bot API."""
import requests

API = "https://api.telegram.org/bot{token}/{method}"


class TelegramError(RuntimeError):
    pass


def call(token, method, **params):
    r = requests.post(API.format(token=token, method=method), json=params, timeout=30)
    data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if not data.get("ok"):
        raise TelegramError(f"{method}: {data.get('description') or r.status_code}")
    return data["result"]


def send_message(token, chat_id, html):
    return call(token, "sendMessage", chat_id=chat_id, text=html, parse_mode="HTML",
                link_preview_options={"is_disabled": True})
