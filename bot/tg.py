"""Минимальный клиент Telegram Bot API без внешних библиотек."""
import json
import os
import sys
import urllib.error
import urllib.request

API_BASE = os.environ.get("TG_API_BASE", "https://api.telegram.org")


def env(name, default=None, required=True):
    value = os.environ.get(name, "").strip() or default
    if required and not value:
        sys.exit(f"Не задан секрет {name}. Добавь его в Settings → Secrets and variables → Actions.")
    return value


TOKEN = env("BOT_TOKEN")
OWNER_ID = int(env("OWNER_ID"))
CHANNEL = env("CHANNEL", default="@tydosoft", required=False)

DRAFT_BUTTONS = {
    "inline_keyboard": [[
        {"text": "✅ Опубликовать", "callback_data": "pub"},
        {"text": "🗑 Пропустить", "callback_data": "skip"},
    ]]
}


class TelegramError(Exception):
    pass


def call(method, http_timeout=60, **params):
    params = {k: v for k, v in params.items() if v is not None}
    data = json.dumps(params).encode("utf-8")
    req = urllib.request.Request(
        f"{API_BASE}/bot{TOKEN}/{method}",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=http_timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except Exception:
            raise TelegramError(f"{method}: HTTP {e.code}") from None
    if not body.get("ok"):
        raise TelegramError(f"{method}: {body.get('description', body)}")
    return body["result"]


def send_draft(text=None, entities=None, html=None):
    """Отправляет владельцу черновик с кнопками. Либо html, либо text+entities."""
    common = dict(
        chat_id=OWNER_ID,
        reply_markup=DRAFT_BUTTONS,
        link_preview_options={"is_disabled": True},
    )
    if html is not None:
        try:
            return call("sendMessage", text=html, parse_mode="HTML", **common)
        except TelegramError as e:
            if "parse" not in str(e).lower() and "entit" not in str(e).lower():
                raise
            # Сломанная разметка: шлём как есть, чтобы черновик не потерялся
            notify(f"⚠️ В черновике сломана HTML-разметка ({e}). Присылаю без форматирования.")
            return call("sendMessage", text=html, **common)
    return call("sendMessage", text=text, entities=entities, **common)


def notify(text):
    return call("sendMessage", chat_id=OWNER_ID, text=text,
                link_preview_options={"is_disabled": True})
