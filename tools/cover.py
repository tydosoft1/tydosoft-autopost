"""Обложка к посту @tydosoft (1280×720 PNG).

Примеры:
  python3 tools/cover.py --out drafts/2026-11-02.png --kicker "🔘 НОВОСТЬ" \
      --title "Spotify добавил ИИ-диджея на русском" --subtitle "Пока в бете, но уже можно попробовать"

  python3 tools/cover.py --out drafts/2026-11-06.png --theme fire --kicker "⚡️ АКЦИЯ" \
      --title "Скидка на все подписки" --big "-10%" --big-label "до 30 ноября" \
      --item "SOLO — 9.3 BYN" --item "DUO — 10.9 BYN" --item "FAMILY — 12.9 BYN"

  python3 tools/cover.py --out x.png --theme violet --kicker "🇮🇳 ИНДИЯ" \
      --title "Годовая подписка подешевела" --big "-40%"

  python3 tools/cover.py --out x.png --kicker "🔘 НОВАЯ ФИШКА" --icon "🤖" --sticker "NEW" \
      --title "ИИ-плейлисты по запросу" --subtitle "Пишешь настроение — получаешь подборку"

Темы: green (по умолчанию), fire (срочные акции), violet (регионы/цены), mono.
Нужен Playwright для Python (в окружении Claude уже стоит).
"""
import argparse
import base64
import html
import pathlib
import re
import sys

from playwright.sync_api import sync_playwright

FONTS = pathlib.Path(__file__).resolve().parent / "fonts"

THEMES = {
    "green":  {"accent": "#2BE36B", "accent2": "#0E7A3A", "ink": "#06140B"},
    "fire":   {"accent": "#FF7A1A", "accent2": "#B3260E", "ink": "#1A0A02"},
    "violet": {"accent": "#A98BFF", "accent2": "#4B2BB8", "ink": "#0F0820"},
    "mono":   {"accent": "#F2F2F2", "accent2": "#5A5A5A", "ink": "#0B0B0B"},
}

TEMPLATE = """<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{font-family:Disp;src:url(data:font/otf;base64,F_DISP);font-weight:900}
@font-face{font-family:Txt;src:url(data:font/otf;base64,F_SEMI);font-weight:600}
@font-face{font-family:Txt;src:url(data:font/otf;base64,F_MED);font-weight:500}
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1280px;height:720px;overflow:hidden}
body{background:#0B0C0B;color:#fff;font-family:Txt,'Inter','DejaVu Sans','Noto Color Emoji',sans-serif;position:relative}
.glow{position:absolute;inset:0;background:
  radial-gradient(900px 600px at 105% 110%, ACCENT2 0%, transparent 60%),
  radial-gradient(700px 500px at -10% -20%, ACCENT2 0%, transparent 55%);opacity:.55}
.grid{position:absolute;inset:0;background-image:
  linear-gradient(rgba(255,255,255,.035) 1px,transparent 1px),
  linear-gradient(90deg,rgba(255,255,255,.035) 1px,transparent 1px);background-size:48px 48px}
.bars{position:absolute;right:64px;top:64px;display:flex;gap:9px;align-items:flex-end;height:64px}
.bars i{display:block;width:12px;border-radius:6px;background:ACCENT}
.wrap{position:absolute;inset:64px 64px 56px 72px;display:flex;flex-direction:column}
.kicker{align-self:flex-start;white-space:nowrap;background:ACCENT;color:INK;font-weight:600;font-size:26px;
  letter-spacing:.06em;padding:10px 22px;border-radius:999px;font-family:Txt,'Inter','Noto Color Emoji',sans-serif}
.main{flex:1;display:flex;gap:48px;align-items:center;min-height:0}
.left{flex:1;min-width:0;display:flex;flex-direction:column;justify-content:center;height:100%}
#title{font-family:Disp,'Inter Display','Noto Color Emoji';font-weight:900;line-height:1.02;
  letter-spacing:-.02em;font-size:@@TSIZE@@px;padding-bottom:6px}
.sub{margin-top:22px;font-size:30px;font-weight:500;color:rgba(255,255,255,.72);line-height:1.3;
  max-height:80px;overflow:hidden}
.items{margin-top:26px;display:flex;flex-direction:column;gap:10px}
.items div{font-size:30px;font-weight:600;display:flex;align-items:center;gap:14px}
.items div:before{content:'';width:12px;height:12px;border-radius:50%;background:ACCENT;flex:none}
.right{flex:none;display:flex;flex-direction:column;align-items:flex-end;justify-content:center;max-width:46%}
#big{font-family:Disp,'Inter Display';font-weight:900;color:ACCENT;font-size:210px;line-height:.9;
  letter-spacing:-.04em;white-space:nowrap;text-shadow:0 0 60px ACCENT2}
.biglabel{margin-top:14px;font-size:30px;font-weight:600;color:#fff;background:rgba(255,255,255,.08);
  border:1px solid rgba(255,255,255,.14);padding:8px 18px;border-radius:14px}
.tile{width:330px;height:330px;border-radius:72px;display:flex;align-items:center;justify-content:center;
  font-size:190px;line-height:1;font-family:'Noto Color Emoji';position:relative;transform:rotate(-6deg);
  background:linear-gradient(145deg,rgba(255,255,255,.14),rgba(255,255,255,.03));
  border:2px solid rgba(255,255,255,.16);box-shadow:0 0 0 10px rgba(255,255,255,.03),0 30px 120px ACCENT2}
.tile:after{content:'';position:absolute;inset:-2px;border-radius:72px;border:3px solid ACCENT;opacity:.55}
.sticker{position:absolute;top:-22px;right:-30px;transform:rotate(12deg);background:ACCENT;color:INK;
  font-family:Disp,'Inter Display';font-weight:900;font-size:34px;padding:8px 18px;border-radius:14px;letter-spacing:.02em}
.right .biglabel{margin-top:34px}
.foot{display:flex;justify-content:space-between;align-items:center;font-size:24px;font-weight:600;
  color:rgba(255,255,255,.55)}
.foot b{color:#fff;font-weight:600}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;background:ACCENT;margin-right:12px;vertical-align:middle}
</style></head><body>
<div class="glow"></div><div class="grid"></div>
<div class="bars"><i style="height:38%"></i><i style="height:80%"></i><i style="height:55%"></i><i style="height:100%"></i><i style="height:30%"></i></div>
<div class="wrap">
  @@KICKER@@
  <div class="main">
    <div class="left"><div id="title">@@TITLE@@</div>@@SUB@@ @@ITEMS@@</div>
    @@RIGHT@@
  </div>
  <div class="foot"><span><span class="dot"></span><b>Мэтью Спотифай</b></span><span>@tydosoft</span></div>
</div>
<script>
function fit(el,min,maxh){let s=parseFloat(getComputedStyle(el).fontSize);
  while((el.scrollHeight>maxh||el.scrollWidth>el.clientWidth+2)&&s>min){s-=3;el.style.fontSize=s+'px'}}
window.doFit=async()=>{await document.fonts.ready;
  const big=document.getElementById('big');
  if(big){let s=210;while(big.scrollWidth>560&&s>90){s-=6;big.style.fontSize=s+'px'}}
  fit(document.getElementById('title'),44,@@TMAXH@@);};
</script></body></html>"""


def font64(name):
    return base64.b64encode((FONTS / name).read_bytes()).decode()


def build(args):
    t = THEMES[args.theme]
    esc = lambda s: html.escape(s or "")
    right, tsize, tmaxh = "", 96, 330
    if args.big:
        right = f'<div class="right"><div id="big">{esc(args.big)}</div>'
        if args.big_label:
            right += f'<div class="biglabel">{esc(args.big_label)}</div>'
        right += "</div>"
        tsize = 80
    elif args.icon:
        sticker = f'<div class="sticker">{esc(args.sticker)}</div>' if args.sticker else ""
        right = f'<div class="right" style="padding-right:24px"><div class="tile">{esc(args.icon)}{sticker}</div>'
        if args.big_label:
            right += f'<div class="biglabel">{esc(args.big_label)}</div>'
        right += "</div>"
        tsize, tmaxh = 84, 400
    items = ""
    if args.item:
        items = '<div class="items">' + "".join(f"<div>{esc(i)}</div>" for i in args.item[:4]) + "</div>"
    # сначала цвета, потом шрифты: в base64 могут встретиться «INK» и т.п.
    style = (TEMPLATE
             .replace("ACCENT2", t["accent2"]).replace("ACCENT", t["accent"]).replace("INK", t["ink"])
             .replace("F_DISP", font64("InterDisplay-Black.otf"))
             .replace("F_SEMI", font64("Inter-SemiBold.otf"))
             .replace("F_MED", font64("Inter-Medium.otf")))
    values = {
        "KICKER": f'<div class="kicker">{esc(args.kicker)}</div>' if args.kicker else "<div></div>",
        "TITLE": esc(args.title),
        "SUB": f'<div class="sub">{esc(args.subtitle)}</div>' if args.subtitle else "",
        "ITEMS": items,
        "RIGHT": right,
        "TSIZE": str(tsize),
        "TMAXH": str(tmaxh),
    }
    # одна замена за проход, чтобы текст пользователя не задел другие метки
    return re.sub(r"@@(\w+)@@", lambda m: values[m.group(1)], style)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--title", required=True, help="главная фраза, до ~60 символов")
    p.add_argument("--kicker", help="плашка сверху: «🔘 НОВОСТЬ», «⚡️ АКЦИЯ», «🇮🇳 ИНДИЯ»")
    p.add_argument("--subtitle", help="строка под заголовком")
    p.add_argument("--big", help="крупная цифра справа: «-10%», «9.3 BYN», «3$»")
    p.add_argument("--big-label", help="подпись под цифрой: «до 30 ноября»")
    p.add_argument("--item", action="append", help="строка списка (до 4), напр. «SOLO — 9.3 BYN»")
    p.add_argument("--icon", help="для новостей: большой эмодзи в плитке справа, напр. «🎧», «🤖», «📱»")
    p.add_argument("--sticker", help="наклейка на плитке: «NEW», «БЕТА», «СКОРО»")
    p.add_argument("--theme", default="green", choices=THEMES)
    argv, raw = [], sys.argv[1:]
    for i, a in enumerate(raw):  # чтобы работало «--big -10%»
        if i and raw[i - 1] in ("--big", "--big-label", "--title", "--subtitle", "--item", "--sticker") and a.startswith("-"):
            argv[-1] = f"{argv[-1]}={a}"
        else:
            argv.append(a)
    args = p.parse_args(argv)

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.set_content(build(args), wait_until="load")
        page.evaluate("window.doFit()")
        page.screenshot(path=str(out), type="png")
        browser.close()
    print(f"Обложка: {out}")


if __name__ == "__main__":
    main()
