#!/usr/bin/env python3
"""Rebuilds the banner lockups static/img/lockup/<lang>.svg in Century Gothic Bold (the font the Coat of Arms guidelines
specify), keeping the official shield exactly as it is in the current files.

    pip install fonttools && python3 tools/make_lockup.py /path/to/centurygothic_bold.ttf

The font is licensed (Monotype) and is not stored in the repository; only the letter outlines go into the SVGs.
Proportions from the guidelines' master lockup (pp. 53-56), x = shield height (126 units): line 1 cap height 0.186x,
aligned to the shield top; text 0.077x right of the shield; line 2 cap height 0.127x, its cap top 0.053x below line 1;
tracking -10 (thousandths of an em). Text white, for the banner photograph. The same files are used by
lurdy.eu and velkoprevorskypalac.eu.
"""
import re
import sys
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

OUT = Path(__file__).resolve().parent.parent / "static" / "img" / "lockup"
NAMES = {"cs": ("MALTÉZSKÝ ŘÁD", "ČESKÁ REPUBLIKA"), "en": ("ORDER OF MALTA", "CZECH REPUBLIC"), "fr": ("ORDRE DE MALTE", "RÉPUBLIQUE TCHÈQUE"),
         "it": ("ORDINE DI MALTA", "REPUBBLICA CECA"), "de": ("DER MALTESERORDEN", "TSCHECHISCHE REPUBLIK")}
X = 126.0                   # shield height
SHIELD_TOP, SHIELD_RIGHT = 0.19, 109.77  # ink box of the shield group in the lockup's coordinates
TRACK = -0.010


def line(font, text, left, baseline, cap):
    gs, cmap = font.getGlyphSet(), font.getBestCmap()
    h = BoundsPen(gs)
    gs[cmap[ord("H")]].draw(h)
    k = cap / h.bounds[3]
    first = BoundsPen(gs)
    gs[cmap[ord(text[0])]].draw(first)
    x = left - first.bounds[0] * k  # the ink, not the advance box, starts at `left`
    pen, box = SVGPathPen(gs), BoundsPen(gs)
    for ch in text:
        g = gs[cmap[ord(ch)]]
        for p in (pen, box):
            g.draw(TransformPen(p, (k, 0, 0, -k, x, baseline)))
        x += (g.width + TRACK * font["head"].unitsPerEm) * k
    return re.sub(r"(\d+\.\d{2})\d+", r"\1", pen.getCommands()), box.bounds


def main(font_path):
    font = TTFont(font_path)
    for lang, (l1, l2) in NAMES.items():
        f = OUT / f"{lang}.svg"
        src = f.read_text()
        shield = src[src.index("<g "):src.index("</g>") + 4]
        left = SHIELD_RIGHT + 0.077 * X
        b1 = SHIELD_TOP + 0.186 * X
        d1, bb1 = line(font, l1, left, b1, 0.186 * X)
        b2 = b1 + 0.053 * X + 0.127 * X
        d2, bb2 = line(font, l2, left, b2, 0.127 * X)
        top = min(bb1[1], bb2[1]) - 0.5
        w = max(bb1[2], bb2[2]) + 4
        h = 126.0 - top
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 {top:.1f} {w:.1f} {h:.1f}" width="{w:.1f}" height="{h:.1f}">'
               f'{shield}<path fill="#fff" d="{d1} {d2}"/></svg>')
        f.write_text(svg, encoding="utf-8")
        print(f.name, f"{w:.1f}×{h:.1f}")


if __name__ == "__main__":
    main(sys.argv[1])
