"""Writes static/img/lockup/<lang>.svg for orderofmalta.int: line 1 (the Order's name) of the official outlined lockups
used by the Czech Grand Priory site (Century Gothic Bold, already outlined; shield unchanged), as the Order's own site shows
one line beside the shield. ES is not produced (no official Spanish lockup). Run: python3 tools/make_lockup_oom.py"""
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
def write(lang, shield, subs, label):
    w = max(bbox(s)[2] for s in subs) + 4
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 -0.9 {w:.1f} 126.9" width="{w:.1f}" height="126.9">{shield}<path fill="#fff" d="{"".join(subs)}"/></svg>'
    (OUT / f"{lang}.svg").write_text(svg); print(lang, label, f"w={w:.1f}")
for lang in ("en", "it", "fr", "de"):
    shield, subs = parts(lang); write(lang, shield, line1(subs), "line 1 of template lockup")
# es: no official Spanish lockup is available. The site uses the shield plus live text (spec section 4) until the Grand Magistry supplies or approves one.
