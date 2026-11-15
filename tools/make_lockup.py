#!/usr/bin/env python3
"""Banner lockups for orderofmalta.int: static/img/lockup/shield.svg and, with the licensed font, <lang>.svg.

    python3 tools/make_lockup.py --shield [--from /path/to/lockup.svg]      # standard library only
    pip install fonttools && python3 tools/make_lockup.py /path/to/centurygothic_bold.ttf

--shield writes shield.svg: the official shield group copied UNCHANGED (same paths, same colours) from an existing lockup
of the same family (default: the Czech Grand Priory site's lockup, the template this site was made from), with the view
box cropped to the shield. The shield is never redrawn or recoloured.

With a font path it writes outlined, single-line lockups <lang>.svg next to the shield. The guidelines' lettering
(Century Gothic Bold) is a licensed font that is not in the repository, so these need the Grand Magistry's approval
and the licensed font (see docs/brand-compliance.md). Until they exist the layout shows the shield and the name as live text.
Proportions from the guidelines' master lockup (pp. 53-56), x = shield height (126 units): line cap height 0.186x aligned
to the shield top; text 0.077x right of the shield; tracking -10 (thousandths of an em). Text white, for the banner photograph.
"""
import re
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "static" / "img" / "lockup"
DEFAULT_SOURCE = Path("/home/user/maltezskyrad/static/img/lockup/en.svg")
# one line per language: the upper-cased short name of the Order (content/site.json -> names[lang].orderShort)
NAMES = {"en": "SOVEREIGN ORDER OF MALTA", "it": "SOVRANO ORDINE DI MALTA", "fr": "ORDRE SOUVERAIN DE MALTE",
         "de": "SOUVERÄNER MALTESERORDEN", "es": "SOBERANA ORDEN DE MALTA"}
X = 126.0                   # shield height
SHIELD_TOP, SHIELD_RIGHT = 0.19, 109.77  # ink box of the shield group in the lockup's coordinates
TRACK = -0.010
SHIELD_VIEWBOX = (-1.0, -0.9, 111.8, 126.9)  # x, y, w, h: the shield plus its outline stroke


def shield_group(src):
    text = Path(src).read_text(encoding="utf-8")
    start = text.index("<g ")
    return text[start:text.index("</g>", start) + 4]


def write_shield(source):
    group = shield_group(source)
    x, y, w, h = SHIELD_VIEWBOX
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x:g} {y:g} {w:g} {h:g}" width="{w:g}" height="{h:g}">{group}</svg>')
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "shield.svg").write_text(svg, encoding="utf-8")
    print("shield.svg", f"{w:g}x{h:g}")


def line(font, text, left, baseline, cap):
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
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


def write_outlined(font_path):
    from fontTools.ttLib import TTFont
    font = TTFont(font_path)
    group = shield_group(OUT / "shield.svg")
    for lang, text in NAMES.items():
        left = SHIELD_RIGHT + 0.077 * X
        base = SHIELD_TOP + 0.186 * X
        d, bb = line(font, text, left, base, 0.186 * X)
        top = min(bb[1], SHIELD_VIEWBOX[1]) - 0.5
        w = bb[2] + 4
        h = 126.0 - top
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 {top:.1f} {w:.1f} {h:.1f}" width="{w:.1f}" height="{h:.1f}">'
               f'{group}<path fill="#fff" d="{d}"/></svg>')
        (OUT / f"{lang}.svg").write_text(svg, encoding="utf-8")
        print(f"{lang}.svg", f"{w:.1f}x{h:.1f}")


def main(argv):
    if "--shield" in argv:
        src = argv[argv.index("--from") + 1] if "--from" in argv else (OUT / "shield.svg" if (OUT / "shield.svg").exists() else DEFAULT_SOURCE)
        write_shield(src)
    else:
        paths = [a for a in argv if not a.startswith("--")]
        if not paths:
            sys.exit(__doc__)
        write_outlined(paths[0])


if __name__ == "__main__":
    main(sys.argv[1:])
