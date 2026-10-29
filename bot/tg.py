"""Минимальный клиент Telegram Bot API без внешних библиотек."""
import json
import mimetypes
import os
import pathlib
import sys
import urllib.error
import urllib.request
import uuid

API_BASE = os.environ.get("TG_API_BASE", "https://api.telegram.org")


def fail(message):
    """Ошибка видна в GitHub (аннотация к запуску) и завершает скрипт."""
    print(f"::error::{message}")
    sys.exit(1)


def env(name, default=None, required=True):
    value = os.environ.get(name, "").strip() or default
    if required and not value:
        fail(f"Не задан секрет {name}. Добавь его в Settings → Secrets and variables → Actions "
             f"(имя ровно {name}, без пробелов).")
    return value


TOKEN = env("BOT_TOKEN")
try:
    OWNER_ID = int(env("OWNER_ID"))
except ValueError:
    fail("Секрет OWNER_ID должен быть числом (твой Telegram ID из @userinfobot), а не @username.")
CHANNEL = env("CHANNEL", default="@tydosoft", required=False)

DRAFT_BUTTONS = {
    "inline_keyboard": [[
        {"text": "✅ Опубликовать", "callback_data": "pub"},
        {"text": "🗑 Пропустить", "callback_data": "skip"},
    ]]
}


class TelegramError(Exception):
    pass


def _multipart(params, files):
    boundary = uuid.uuid4().hex
    parts = []
    for key, value in params.items():
        if not isinstance(value, str):
            value = json.dumps(value)
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n'.encode()
                     + value.encode("utf-8") + b"\r\n")
    for key, path in files.items():
        path = pathlib.Path(path)
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"; '
                     f'filename="{path.name}"\r\nContent-Type: {mime}\r\n\r\n'.encode()
                     + path.read_bytes() + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def call(method, http_timeout=60, files=None, **params):
    params = {k: v for k, v in params.items() if v is not None}
    if files:
        data, ctype = _multipart(params, files)
    else:
        data, ctype = json.dumps(params).encode("utf-8"), "application/json"
    req = urllib.request.Request(
        f"{API_BASE}/bot{TOKEN}/{method}",
        data=data,
        headers={"Content-Type": ctype},
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


def biggest_photo(msg):
    photos = msg.get("photo") or []
    return photos[-1]["file_id"] if photos else None


def send_post(chat_id, text=None, entities=None, html=None, photo_path=None, photo_id=None,
              reply_markup=None):
    """Текстовый пост или пост с картинкой (подпись до 1024 символов)."""
    photo = photo_id
    files = {"photo": photo_path} if photo_path else None
    if html is not None:
        body = {"parse_mode": "HTML"}
        content = html
    else:
        body = {"entities" if not (photo or files) else "caption_entities": entities}
        content = text
    if photo or files:
        return call("sendPhoto", chat_id=chat_id, photo=photo, caption=content,
                    reply_markup=reply_markup, files=files, **body)
    return call("sendMessage", chat_id=chat_id, text=content, reply_markup=reply_markup,
                link_preview_options={"is_disabled": True}, **body)


def send_draft(text=None, entities=None, html=None, photo_path=None, photo_id=None):
    """Отправляет владельцу черновик с кнопками. Либо html, либо text+entities."""
    kw = dict(text=text, entities=entities, html=html, photo_path=photo_path,
              photo_id=photo_id, reply_markup=DRAFT_BUTTONS)
    try:
        return send_post(OWNER_ID, **kw)
    except TelegramError as e:
        err = str(e).lower()
        if (photo_path or photo_id) and "caption is too long" in err:
            notify("⚠️ Текст длиннее 1024 символов — Telegram не даёт столько под картинкой. "
                   "Присылаю без картинки.")
            kw.update(photo_path=None, photo_id=None)
            return send_post(OWNER_ID, **kw)
        if html is not None and ("parse" in err or "entit" in err):
            # Сломанная разметка: шлём как есть, чтобы черновик не потерялся
            notify(f"⚠️ В черновике сломана HTML-разметка ({e}). Присылаю без форматирования.")
            kw.update(html=None, text=html)
            return send_post(OWNER_ID, **kw)
        raise


def explain(err):
    """Понятная подсказка к частым ошибкам Telegram."""
    e = str(err).lower()
    if "unauthorized" in e or "not found" in e and "chat" not in e:
        return "Неверный BOT_TOKEN — скопируй токен из @BotFather заново."
    if "chat not found" in e or "can't initiate" in e or "blocked" in e:
        return ("Бот не может написать тебе: открой своего бота в Telegram и нажми Start, "
                "и проверь, что OWNER_ID — именно твой ID из @userinfobot.")
    if "administrator" in e or "not enough rights" in e or "need" in e and "rights" in e:
        return "Бот не админ канала или у него нет права «Публикация сообщений»."
    return ""


def notify(text):
    return call("sendMessage", chat_id=OWNER_ID, text=text,
                link_preview_options={"is_disabled": True})
