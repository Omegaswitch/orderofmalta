"""Writes static/img/lockup/<lang>.svg for orderofmalta.int: line 1 (the Order's name) of the official outlined lockups
used by the Czech Grand Priory site (Century Gothic Bold, already outlined; shield unchanged). ES is composed from the official
FR/IT letter outlines (approved by the Grand Magistry, 15 Nov 2026). Run: python3 -I tools/make_lockup_oom.py"""
import re, sys
from pathlib import Path
SRC = Path("/home/user/maltezskyrad/static/img/lockup"); OUT = Path("/home/user/orderofmalta/static/img/lockup")
NUM = re.compile(r"-?\d+(?:\.\d+)?")
def parts(lang):
    t = (SRC / f"{lang}.svg").read_text()
    head_end = t.index("</g>") + 4
    shield = t[t.index("<g "):head_end]
    d = re.search(r'<path fill="#fff" d="([^"]+)"/>\s*</svg>', t).group(1)
    subs = ["M" + s for s in d.split("M") if s.strip()]
    return shield, subs
TOK = re.compile(r"[A-Za-z]|-?\d+(?:\.\d+)?")
def coords(sub):
    """yield (kind, token) with kind in 'c','x','y','n' (command/x/y/number)"""
    cmd, k = None, 0
    for t in TOK.findall(sub):
        if t.isalpha():
            cmd, k = t, 0; yield "c", t; continue
        if cmd in "HV": yield ("x" if cmd == "H" else "y"), t
        else: yield ("x" if k % 2 == 0 else "y"), t; k += 1
def bbox(sub):
    xs = [float(t) for kd, t in coords(sub) if kd == "x"]; ys = [float(t) for kd, t in coords(sub) if kd == "y"]
    return min(xs), min(ys), max(xs), max(ys)
def line1(subs):
    return [s for s in subs if bbox(s)[3] < 25.5]
def glyphs(subs):
    # group subpaths whose x-range overlaps (counters of O, R, D, A)
    gs = []
    for s in sorted(subs, key=lambda s: bbox(s)[0]):
        b = bbox(s)
        if gs and b[0] < gs[-1][1][2] - 0.5:
            g = gs[-1]; g[0].append(s); g[1] = (min(g[1][0], b[0]), min(g[1][1], b[1]), max(g[1][2], b[2]), max(g[1][3], b[3]))
        else:
            gs.append([[s], b])
    return gs
def shift(sub, dx):
    out = []
    for kd, t in coords(sub):
        out.append(t if kd in "cy" else f"{float(t)+dx:.2f}")
    r = ""
    for t in out:
        r += t if t.isalpha() else ((" " if r and not r[-1].isalpha() else "") + t)
    return r
def write(lang, shield, subs, label):
    w = max(bbox(s)[2] for s in subs) + 4
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 -0.9 {w:.1f} 126.9" width="{w:.1f}" height="126.9">{shield}<path fill="#fff" d="{"".join(subs)}"/></svg>'
    (OUT / f"{lang}.svg").write_text(svg); print(lang, label, f"w={w:.1f}", len(glyphs(subs)), "glyphs")
for lang in ("en", "it", "fr", "de"):
    shield, subs = parts(lang); write(lang, shield, line1(subs), "line 1 of template lockup")
# es: ORDEN DE MALTA from fr "ORDRE DE MALTE" (+ N from it "ORDINE")
shield, fr = parts("fr"); fg = glyphs(line1(fr))           # O R D R E | D E | M A L T E
_, it = parts("it"); ig = glyphs(line1(it))                 # O R D I N E | D I | M A L T A
assert len(fg) == 12 and len(ig) == 13, (len(fg), len(ig))
gap = lambda gs, i: gs[i][1][0] - gs[i-1][1][2]             # space before glyph i in its source
# sequence: (glyph, gap before it)
seq = [(fg[0], 0), (fg[1], gap(fg,1)), (fg[2], gap(fg,2)), (fg[4], gap(fg,4)), (ig[4], gap(ig,4)),   # O R D E N
       (fg[5], gap(fg,5)), (fg[6], gap(fg,6)),                                                       # _D E
       (fg[7], gap(fg,7)), (fg[8], gap(fg,8)), (fg[9], gap(fg,9)), (fg[10], gap(fg,10)), (ig[12], gap(ig,12))]  # _M A L T A
x = fg[0][1][0]; out = []
for g, gp in seq:
    x += gp; dx = x - g[1][0]; out += [shift(s, dx) for s in g[0]]; x += g[1][2] - g[1][0]
write("es", shield, out, "composed from official fr/it outlines")
