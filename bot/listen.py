"""Обрабатывает нажатия кнопок и сообщения владельца боту.

✅ Опубликовать — пост уходит в канал (с тем же форматированием).
🗑 Пропустить   — черновик помечается как пропущенный.
Ответ на черновик своим текстом — бот присылает новую версию с кнопками
(картинка, если была, остаётся). Ответ фото с подписью — новая версия с этим фото.
Любой свой текст или фото с подписью боту — тоже становится черновиком с кнопками.

Использование: python3 bot/listen.py --minutes 30   (слушать 30 минут)
               python3 bot/listen.py --minutes 0    (один быстрый проход)
"""
import argparse
import time

import tg

HELP = (
    "Я присылаю черновики постов для {channel}.\n\n"
    "✅ — опубликовать в канал\n"
    "🗑 — пропустить\n"
    "✏️ Поправить текст — ответь на черновик своей версией, пришлю новую с кнопками (картинка останется).\n"
    "🖼 Другая картинка — ответь на черновик фото с подписью.\n"
    "Свой пост — просто пришли мне текст или фото с подписью, он тоже станет черновиком.\n\n"
    "Отвечаю не мгновенно: проверяю сообщения раз в ~10 минут."
)


def safe(method, **params):
    try:
        return tg.call(method, **params)
    except tg.TelegramError as e:
        print(f"(не критично) {e}")
        return None


def is_draft(msg):
    rows = (msg.get("reply_markup") or {}).get("inline_keyboard") or []
    return any(b.get("callback_data") == "pub" for row in rows for b in row)


def mark(msg, text, url=None):
    button = {"text": text, "url": url} if url else {"text": text, "callback_data": "noop"}
    safe("editMessageReplyMarkup", chat_id=msg["chat"]["id"], message_id=msg["message_id"],
         reply_markup={"inline_keyboard": [[button]]})


def content_of(msg):
    """Текст/подпись, форматирование и картинка сообщения — для повторной отправки."""
    if msg.get("photo"):
        return dict(text=msg.get("caption"), entities=msg.get("caption_entities"),
                    photo_id=tg.biggest_photo(msg))
    return dict(text=msg.get("text"), entities=msg.get("entities"))


def post_link(post):
    username = (post.get("chat") or {}).get("username")
    if not username and tg.CHANNEL.startswith("@"):
        username = tg.CHANNEL[1:]
    return f"https://t.me/{username}/{post['message_id']}" if username else None


def handle_callback(cq, handled):
    answer = lambda text=None: safe("answerCallbackQuery", callback_query_id=cq["id"], text=text)
    if cq["from"]["id"] != tg.OWNER_ID:
        return answer("Нет доступа")
    msg = cq.get("message") or {}
    if not (msg.get("text") or msg.get("photo")):
        return answer("Это сообщение уже недоступно")
    key = (msg["chat"]["id"], msg["message_id"])
    action = cq.get("data")

    if action in ("pub", "skip") and (key in handled or not is_draft(msg)):
        return answer("Уже обработано")

    if action == "pub":
        try:
            post = tg.send_post(tg.CHANNEL, **content_of(msg))
        except tg.TelegramError as e:
            answer("Не получилось 😕")
            tg.notify(f"❌ Не получилось опубликовать в {tg.CHANNEL}: {e}\n\n"
                      "Проверь, что бот — админ канала с правом «Публикация сообщений».")
            return
        handled.add(key)
        mark(msg, "✅ Опубликовано — открыть", post_link(post))
        answer("Опубликовано ✅")
        print(f"Опубликовал черновик {key} → {post_link(post)}")
    elif action == "skip":
        handled.add(key)
        mark(msg, "🗑 Пропущено")
        answer("Пропустил")
        print(f"Пропустил черновик {key}")
    else:
        answer()


def handle_message(msg, handled):
    if msg.get("chat", {}).get("type") != "private":
        return
    if msg.get("from", {}).get("id") != tg.OWNER_ID:
        return  # чужим не отвечаем
    text = msg.get("text")
    if not text and not msg.get("photo"):
        tg.notify("Умею текстовые посты и посты с одной картинкой. Видео, файлы и альбомы пока не поддерживаю.")
        return
    if text and text.strip().split()[0] in ("/start", "/help"):
        tg.notify(HELP.format(channel=tg.CHANNEL) + f"\n\nТвой Telegram ID: {msg['from']['id']}")
        return

    replied = msg.get("reply_to_message") or {}
    new = content_of(msg)
    if replied and is_draft(replied):
        key = (replied["chat"]["id"], replied["message_id"])
        if key not in handled:
            handled.add(key)
            mark(replied, "♻️ Заменён новой версией")
        if text and replied.get("photo"):
            new["photo_id"] = tg.biggest_photo(replied)  # поправил текст — картинка остаётся
    tg.send_draft(**new)
    print("Прислал новую версию черновика")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--minutes", type=float, default=0)
    args = parser.parse_args()

    deadline = time.time() + args.minutes * 60
    offset = None
    handled = set()
    while True:
        wait = int(max(0, min(50, deadline - time.time())))
        try:
            updates = tg.call("getUpdates", http_timeout=wait + 20, offset=offset,
                              timeout=wait, allowed_updates=["message", "callback_query"])
        except tg.TelegramError as e:
            if "conflict" in str(e).lower():
                print(f"Другой процесс уже слушает бота, выхожу: {e}")
                return
            raise
        for upd in updates:
            offset = upd["update_id"] + 1
            try:
                if "callback_query" in upd:
                    handle_callback(upd["callback_query"], handled)
                elif "message" in upd:
                    handle_message(upd["message"], handled)
            except Exception as e:  # одно кривое обновление не должно ронять бота
                print(f"Ошибка на обновлении {upd['update_id']}: {e!r}")
                safe("sendMessage", chat_id=tg.OWNER_ID, text=f"⚠️ Ошибка бота: {e}"[:4000])
        if time.time() >= deadline and not updates:
            break
    if offset is not None:  # подтверждаем обработанные обновления
        safe("getUpdates", offset=offset, timeout=0, limit=1)


if __name__ == "__main__":
    try:
        main()
    except tg.TelegramError as e:
        tg.fail(f"Telegram: {e}. {tg.explain(e)}")
