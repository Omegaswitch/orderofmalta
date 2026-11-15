#!/usr/bin/env python3
"""Builds static/img/og-<lang>.jpg (en, it, fr, de, es), the 1200x630 link-preview cards: a photograph under a dark veil,
the lockup for that language and a red strip.

The lockup is static/img/lockup/<lang>.svg (outlined, white lettering) when it exists. Otherwise the official shield
(static/img/lockup/shield.svg, unchanged) with the Order's name set in the site's own Asap 700 (static/fonts).
Developer tool, not a build dependency; the output is committed.

    pip install playwright pillow && python3 tools/make_og.py
"""
import base64
import io
import json
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PHOTO = ROOT / "static" / "img" / "banner" / "banner-photo.webp"
FONT = ROOT / "static" / "fonts" / "asap-latin-700-normal.woff2"
FONT_EXT = ROOT / "static" / "fonts" / "asap-latin-ext-700-normal.woff2"
PHOTO_CSS = "top:0;height:630px;width:auto;left:-2690px;filter:blur(1.2px)"  # the flag
LANGS = ("en", "it", "fr", "de", "es")
RED = "#e31818"
NAMES = json.loads((ROOT / "content" / "site.json").read_text(encoding="utf-8"))["names"]


def b64(path, mime):
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def card(page, lang):
    outlined = ROOT / "static" / "img" / "lockup" / f"{lang}.svg"
    if outlined.exists():
        mark = f'<img src="{b64(outlined, "image/svg+xml")}" style="position:absolute;left:68px;top:50%;transform:translateY(-54%);height:206px;width:auto" alt="">'
        fonts = ""
    else:
        name = NAMES[lang]["orderShort"].upper()
        mark = (f'<div style="position:absolute;left:68px;top:50%;transform:translateY(-54%);display:flex;align-items:center;gap:36px">'
                f'<img src="{b64(ROOT / "static/img/lockup/shield.svg", "image/svg+xml")}" style="height:250px;width:auto" alt="">'
                f'<div style="font:700 66px/1.12 Asap,sans-serif;color:#fff;letter-spacing:.01em;max-width:700px">{name}</div></div>')
        fonts = (f"@font-face{{font-family:Asap;font-weight:700;src:url({b64(FONT, 'font/woff2')}) format('woff2');unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+2074,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD}}"
                 f"@font-face{{font-family:Asap;font-weight:700;src:url({b64(FONT_EXT, 'font/woff2')}) format('woff2');unicode-range:U+0100-02AF,U+1E00-1EFF,U+2020,U+20A0-20AB,U+20AD-20CF,U+2113,U+2C60-2C7F,U+A720-A7FF}}")
    page.set_content(f'''<!doctype html><style>{fonts}</style><body style="margin:0;width:1200px;height:630px;position:relative;overflow:hidden;background:#1d2a3a">
<img src="{b64(PHOTO, 'image/webp')}" style="position:absolute;{PHOTO_CSS}" alt="">
<div style="position:absolute;inset:0;background:linear-gradient(90deg,rgba(14,22,30,.74) 0%,rgba(14,22,30,.62) 45%,rgba(14,22,30,.45) 70%,rgba(14,22,30,.55) 100%)"></div>
{mark}
<div style="position:absolute;left:0;right:0;bottom:0;height:18px;background:{RED}"></div></body>''')
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(300)
    out = ROOT / "static" / "img" / f"og-{lang}.jpg"
    Image.open(io.BytesIO(page.screenshot())).convert("RGB").save(out, "JPEG", quality=86, progressive=True, optimize=True)
    print(out.name, out.stat().st_size)


def main():
    exe = "/opt/pw-browsers/chromium" if Path("/opt/pw-browsers/chromium").is_file() else None
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=exe)
        page = b.new_page(viewport={"width": 1200, "height": 630})
        for lang in LANGS:
            card(page, lang)
        b.close()


if __name__ == "__main__":
    main()
