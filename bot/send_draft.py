"""Отправляет черновики из drafts/ владельцу канала на проверку.

Использование: python3 bot/send_draft.py drafts/2026-11-02.html [ещё файлы...]
Если рядом лежит drafts/2026-11-02.png (или .jpg) — пост уйдёт с картинкой.
"""
import pathlib
import sys

import tg

IMAGE_EXTS = (".png", ".jpg", ".jpeg")  # картинка с тем же именем, что и .html, уйдёт вместе с постом


def main(paths):
    paths = [p for p in paths if p.strip() and not p.endswith(".gitkeep")]
    if not paths:
        print("Новых черновиков нет.")
        return
    for path in paths:
        file = pathlib.Path(path)
        if not file.exists():
            print(f"Пропускаю {path}: файла нет (удалён?)")
            continue
        html = file.read_text(encoding="utf-8").strip()
        if not html:
            print(f"Пропускаю {path}: пустой файл")
            continue
        image = next((file.with_suffix(ext) for ext in IMAGE_EXTS
                      if file.with_suffix(ext).exists()), None)
        tg.notify(f"📝 Новый пост на проверку · {file.stem}\n"
                  "✅ — опубликовать в канал, 🗑 — пропустить.\n"
                  "Хочешь поправить — ответь на черновик своей версией текста.")
        msg = tg.send_draft(html=html, photo_path=image)
        print(f"Отправил {path}{' + ' + image.name if image else ''} (message_id={msg['message_id']})")


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except tg.TelegramError as e:
        tg.fail(f"Telegram: {e}. {tg.explain(e)}")
