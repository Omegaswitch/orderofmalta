#!/usr/bin/env python3
"""Static site generator for orderofmalta.int (Grand Magistry of the Sovereign Order of Malta).
Python 3.10+, standard library only (Pillow is used by tools/, never by the build).

    python3 build.py                 preview build into dist/ (noindex, content-status labels shown)
    python3 build.py --production    production build (indexable, no status labels)
    python3 build.py serve [port]    preview build, then serve dist/ with _headers and _redirects applied

`--offline` is accepted and does nothing: the build never touches the network.
Environment: OOM_CONTENT = content root (default content/), OOM_DIST = output folder (default dist/).
The contract between build, frontend and backend is docs/build-spec.md (sections 2-5).
"""
import html
import json
import math
import os
import re
import shutil
import struct
import sys
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit

ROOT = Path(__file__).resolve().parent
CONTENT = Path(os.environ.get("OOM_CONTENT") or ROOT / "content")
STATIC = ROOT / "static"
DIST = Path(os.environ.get("OOM_DIST") or ROOT / "dist")
PRODUCTION = "--production" in sys.argv
ASSET_VERSION = datetime.now().strftime("%Y%m%d%H%M")
esc = lambda s: html.escape(str(s if s is not None else ""), quote=True)

WARNINGS, ERRORS = [], []


def warn(msg):
    WARNINGS.append(msg)


def _load_json(name, default=None):
    for base in (CONTENT, ROOT / "content"):
        f = base / name
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
    return default


SITE = _load_json("site.json")
I18N = _load_json("i18n.json")
if not SITE or not I18N:
    sys.exit("content/site.json and content/i18n.json are required")
LANGS = SITE["languages"]
DEFAULT_LANG = LANGS[0]
SEC = SITE["sections"]
PER_PAGE = int(SITE.get("perPage", 12))
EDITOR_URL = SITE.get("editorUrl", "/editor/")
BASE_HOST = urlsplit(SITE["baseUrl"]).hostname or ""
INTERNAL_HOSTS = {BASE_HOST, BASE_HOST.removeprefix("www.")}
LOCALES = {"en": "en_GB", "it": "it_IT", "fr": "fr_FR", "de": "de_DE", "es": "es_ES"}
VIDEO_PROVIDERS = {"youtube": "YouTube", "vimeo": "Vimeo"}


def sec(key, lang):
    return SEC[key][lang]


def home_url(lang):
    return sec("home", lang)


HOME_URLS = {SEC["home"][l] for l in LANGS}


# ---------------------------------------------------------------- time

try:
    from zoneinfo import ZoneInfo
    BUILD_TIME = datetime.now(ZoneInfo(SITE.get("timezone", "Europe/Rome"))).strftime("%Y-%m-%dT%H:%M")  # Vercel builds in UTC
except Exception:
    BUILD_TIME = datetime.now().strftime("%Y-%m-%dT%H:%M")


def due(date):
    """True when a dated item is not in the future (site-local time)."""
    d = str(date or "")
    if len(d) == 10:
        d += "T00:00"
    return d[:16] <= BUILD_TIME


# ---------------------------------------------------------------- content

DOC_SPLIT = "---\n"


def read_doc(path):
    text = path.read_text(encoding="utf-8")
    _, meta, body = text.split(DOC_SPLIT, 2)
    return json.loads(meta), body.strip()


def safe_url(u):
    return isinstance(u, str) and u.startswith("/") and ".." not in u.split("/") and "\\" not in u and "?" not in u and "#" not in u


def _content_path(f):
    try:
        return "content/" + f.relative_to(CONTENT).as_posix()
    except ValueError:
        return f.as_posix()


def load_items(kind, typ):
    base = CONTENT / kind
    found = []
    if not base.exists():
        return found
    for f in sorted(base.rglob("index.html" if kind == "pages" else "*.html")):
        try:
            meta, body = read_doc(f)
        except Exception as e:
            warn(f"{_content_path(f)}: unreadable ({e})")
            continue
        meta.setdefault("type", typ)
        need = ("url", "title", "lang") + (("date",) if typ != "page" else ())
        if any(not meta.get(k) for k in need) or not safe_url(meta["url"]) or not meta["url"].endswith("/"):
            warn(f"{_content_path(f)}: missing or invalid {', '.join(k for k in need if not meta.get(k)) or 'url'}; skipped")
            continue
        if meta["lang"] not in LANGS:
            warn(f"{_content_path(f)}: unknown language {meta['lang']}; skipped")
            continue
        if typ != "page":
            meta["date"] = str(meta["date"])[:16]
        found.append({**meta, "body": body, "src": _content_path(f)})
    return found


ALL_PAGES = load_items("pages", "page")
ALL_NEWS = load_items("news", "news")
ALL_PRESS = load_items("press", "press")
ALL_GALLERIES = load_items("galleries", "gallery")
for _lst in (ALL_NEWS, ALL_PRESS, ALL_GALLERIES):
    _lst.sort(key=lambda n: (n["date"], n["title"]), reverse=True)

# A post marked draft, or dated in the future, stays in the repository but is not built until it is due.
NEWS = [n for n in ALL_NEWS if not n.get("draft") and due(n["date"])]
PRESS = [n for n in ALL_PRESS if not n.get("draft") and due(n["date"])]
GALLERIES = [n for n in ALL_GALLERIES if not n.get("draft") and due(n["date"])]
PAGES = {}
for _p in ALL_PAGES:
    if _p["url"] in PAGES:
        warn(f"duplicate page url {_p['url']} ({_p['src']})")
    PAGES[_p["url"]] = _p

for _n in ALL_NEWS:  # a bare year is the news archive of that year
    if re.fullmatch(r"\d{4}", _n["url"].strip("/").split("/")[-1]):
        ERRORS.append(f"news slug is a bare year (collides with the year archive): {_n['url']} ({_n['src']})")


def by_lang(items, lang):
    return [i for i in items if i["lang"] == lang]


COLL = {l: {} for l in LANGS}
for _l in LANGS:
    for _name in ("publications", "in-the-news"):
        _f = CONTENT / "collections" / _l / f"{_name}.json"
        if _f.exists():
            try:
                COLL[_l][_name] = json.loads(_f.read_text(encoding="utf-8"))
            except Exception as e:
                warn(f"{_content_path(_f)}: unreadable ({e})")
MENUS = _load_json("menus.json", {}) or {}
CATS = _load_json("translations/categories.json", {}) or {}
REDIRECT_FILE = _load_json("redirects.json", []) or []
REDIR_MAP = {r["from"]: r["to"] for r in REDIRECT_FILE if isinstance(r, dict) and r.get("from") and r.get("to")}

# sections the build owns: a page the importer wrote at one of these URLs supplies only the intro text
for _l in LANGS:
    _wanted = {"pressList": ("press-releases", "pressReleases")}
    for _key, (_tpl, _title) in _wanted.items():
        _u = sec(_key, _l)
        if _u not in PAGES:
            PAGES[_u] = {"type": "page", "lang": _l, "url": _u, "title": I18N[_l][_title], "template": _tpl, "body": "", "parent": None,
                         "order": 0, "translations": {}, "src": "(synthetic)"}
    for _name, _tpl in (("publications", "publications"), ("in-the-news", "in-the-news")):
        _c = COLL[_l].get(_name)
        if _c and safe_url(_c.get("url", "")) and _c["url"] not in PAGES:
            PAGES[_c["url"]] = {"type": "page", "lang": _l, "url": _c["url"], "title": _c.get("title") or I18N[_l]["publications" if _name == "publications" else "inTheNews"],
                                "template": _tpl, "body": "", "parent": None, "order": 0, "translations": {}, "src": "(synthetic)"}
ALL_PAGES = list(PAGES.values())
RESERVED = {sec(k, l) for k in ("news", "galleries", "search", "gdpr") for l in LANGS} | {home_url(l) for l in LANGS} | {EDITOR_URL}

# ---------------------------------------------------------------- translations (the WPML group of each item)

PUBLISHED = {i["url"]: i for i in [*PAGES.values(), *NEWS, *PRESS, *GALLERIES]}
ALT = {}
for _i in PUBLISHED.values():
    _group = {l: u for l, u in (_i.get("translations") or {}).items() if l in LANGS and u in PUBLISHED}
    for _l, _u in (_i.get("translations") or {}).items():
        if _l in LANGS and _u not in PUBLISHED and _u != _i["url"]:
            warn(f"translation target not on disk: {_i['url']} -> {_l} {_u}")
    _group[_i["lang"]] = _i["url"]
    ALT[_i["url"]] = _group
for _i in list(PUBLISHED.values()):  # reciprocal links, so hreflang is valid in both directions
    for _l, _u in list(ALT[_i["url"]].items()):
        if _u != _i["url"] and _u in ALT:
            if ALT[_u].get(_i["lang"]) != _i["url"]:
                if _i["lang"] not in ALT[_u]:
                    warn(f"translations are not symmetric: {_i['url']} -> {_u}")
                    ALT[_u][_i["lang"]] = _i["url"]


def section_alt(key):
    return {l: sec(key, l) for l in LANGS}


for _key in ("home", "news", "pressList", "galleries", "search", "gdpr"):
    for _u in section_alt(_key).values():
        ALT[_u] = section_alt(_key)


def alts_for(url):
    return ALT.get(url) or {}


def alt_links(alt):
    """hreflang + x-default (English, the default language)."""
    out = {l: alt[l] for l in LANGS if l in alt}
    if len(out) < 2:
        return {}
    if DEFAULT_LANG in out:
        out["x-default"] = out[DEFAULT_LANG]
    return out


def switch_target(lang, url, target, section=None):
    """Link for language `target` from page `url`: the real translation, else that language's section listing, else home."""
    found = (ALT.get(url) or {}).get(target)
    if found:
        return found
    if section:
        return sec(section, target)
    item = PUBLISHED.get(url)
    if item:
        if item["type"] == "news":
            return sec("news", target)
        if item["type"] == "press":
            return sec("pressList", target)
        if item["type"] == "gallery":
            return sec("galleries", target)
        seen, p = set(), item
        while p and p.get("parent") and p["parent"] not in seen:  # an untranslated page leads to its nearest translated ancestor
            seen.add(p["parent"])
            p = PAGES.get(p["parent"])
            if p and ALT.get(p["url"], {}).get(target):
                return ALT[p["url"]][target]
    return home_url(target)


# ---------------------------------------------------------------- categories

def cat_term(key, lang):
    return ((CATS.get(key) or {}).get("terms") or {}).get(lang)


def cat_name(key, lang):
    t = cat_term(key, lang) or cat_term(key, DEFAULT_LANG)
    return t["name"] if t else key.replace("-", " ").title()


def cat_url(key, lang):
    t = cat_term(key, lang)
    return t["url"] if t and safe_url(t.get("url", "")) else None


def cat_descendants(key):
    out = {key}
    for k, v in CATS.items():
        if v.get("parent") == key:
            out |= cat_descendants(k)
    return out


def cat_members(key, items):
    keys = cat_descendants(key)
    return [n for n in items if keys & set(n.get("categories") or [])]


# ---------------------------------------------------------------- helpers

MISSING_MEDIA = set()


@lru_cache(maxsize=None)
def _image_info(rel_url):
    f = STATIC / unquote(rel_url.lstrip("/"))
    try:
        b = f.read_bytes()[:65536]
    except OSError:
        if rel_url.startswith("/media/"):
            MISSING_MEDIA.add(rel_url)
        return None
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", b[16:24])
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        c = b[12:16]
        if c == b"VP8 ":
            w, h = struct.unpack("<HH", b[26:30])
            return w & 0x3FFF, h & 0x3FFF
        if c == b"VP8L":
            v = int.from_bytes(b[21:25], "little")
            return (v & 0x3FFF) + 1, ((v >> 14) & 0x3FFF) + 1
        if c == b"VP8X":
            return int.from_bytes(b[24:27], "little") + 1, int.from_bytes(b[27:30], "little") + 1
    if b[:2] == b"\xff\xd8":
        i = 2
        while i < len(b) - 9:
            if b[i] != 0xFF:
                i += 1
                continue
            marker, length = b[i + 1], struct.unpack(">H", b[i + 2:i + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", b[i + 5:i + 9])
                return w, h
            i += 2 + length
    return None


def image_size(rel_url):
    """Width/height of a local JPEG, PNG or WebP (for layout-stable <img>)."""
    return _image_info(rel_url)


def local_exists(rel_url):
    return (STATIC / unquote(rel_url.lstrip("/"))).is_file()


def small_variant(src):
    """The `-480.webp` sibling the importer writes for images wider than 640 px, if it exists."""
    if src.startswith("/media/") and src.endswith(".webp") and not src.endswith("-480.webp"):
        small = src[:-5] + "-480.webp"
        if local_exists(small):
            return small
    return None


def auto_srcset(src):
    small = small_variant(src)
    if not small:
        return None
    a, b = image_size(small), image_size(src)
    if a and b and a[0] < b[0]:
        return f"{small} {a[0]}w, {src} {b[0]}w"
    return None


def img(src, alt="", cls="", sizes=None, eager=False, srcset=None):
    wh = image_size(src)
    dims = f' width="{wh[0]}" height="{wh[1]}"' if wh else ""
    load = 'fetchpriority="high"' if eager else 'loading="lazy"'
    srcset = srcset or (auto_srcset(src) if sizes else None)
    responsive = f' srcset="{esc(srcset)}" sizes="{esc(sizes)}"' if srcset and sizes else ""
    return f'<img class="ph-img{" " + cls if cls else ""}" src="{esc(src)}"{responsive} alt="{esc(alt)}"{dims} {load} decoding="async">'


def is_external(u):
    p = urlsplit(u or "")
    return p.scheme in ("http", "https") and (p.hostname or "") not in INTERNAL_HOSTS


def href_attr(u):
    return f'href="{esc(u)}"' + (' rel="noopener"' if is_external(u) else "")


def plain(html_text, n=180):
    t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", html_text or ""))).strip()
    return t if len(t) <= n else t[: t.rfind(" ", 0, n)] + "…"


def fmt_date(iso, lang):
    s = str(iso)
    m = I18N[lang]["months"]
    if len(s) == 7:
        d = datetime.fromisoformat(s + "-01")
        return f"{m[d.month - 1]} {d.year}"
    d = datetime.fromisoformat(s[:10])
    if lang == "de":
        return f"{d.day}. {m[d.month - 1]} {d.year}"
    if lang == "es":
        return f"{d.day} de {m[d.month - 1]} de {d.year}"
    return f"{d.day} {m[d.month - 1]} {d.year}"


def tr_fmt(s, **kw):
    for k, v in kw.items():
        s = s.replace("{" + k + "}", str(v))
    return s


def page_url(base, n):
    return base if n == 1 else f"{base}page/{n}/"


# ---------------------------------------------------------------- body (the vocabulary of spec 3.5)

VIDEO_PATTERNS = [
    ("youtube", re.compile(r"^https?://(?:www\.|m\.)?youtube\.com/watch\?(?:[^#]*&)?v=([\w-]{6,20})")),
    ("youtube", re.compile(r"^https?://youtu\.be/([\w-]{6,20})")),
    ("youtube", re.compile(r"^https?://(?:www\.)?youtube(?:-nocookie)?\.com/embed/([\w-]{6,20})")),
    ("vimeo", re.compile(r"^https?://(?:www\.)?vimeo\.com/(\d+)")),
    ("vimeo", re.compile(r"^https?://player\.vimeo\.com/video/(\d+)")),
]
UNKNOWN_EMBEDS = []


def parse_video(url):
    u = html.unescape(url or "").strip()
    for provider, rx in VIDEO_PATTERNS:
        m = rx.match(u)
        if m:
            return provider, m.group(1)
    return None


def embed_html(provider, vid, title, lang):
    t, name = I18N[lang], VIDEO_PROVIDERS[provider]
    if provider == "youtube":
        src = f"https://www.youtube-nocookie.com/embed/{vid}?autoplay=1&rel=0"
        watch = f"https://www.youtube.com/watch?v={vid}"
        poster = f"/media/embeds/youtube-{vid}.webp"
    else:
        src = f"https://player.vimeo.com/video/{vid}?autoplay=1&dnt=1"
        watch, poster = f"https://vimeo.com/{vid}", None
    img_html = ""
    if poster and local_exists(poster):
        wh = image_size(poster) or (480, 360)
        img_html = f'<img class="embed-poster ph-img" src="{poster}" alt="" width="{wh[0]}" height="{wh[1]}" loading="lazy" decoding="async">'
    return (f'<figure class="embed" data-embed="{provider}" data-src="{esc(src)}" data-state="idle">'
            f'<button class="embed-load" type="button" aria-label="{esc(tr_fmt(t["embedPlay"], title=title))}">{img_html}'
            f'<span class="embed-play" aria-hidden="true"></span><span class="embed-title">{esc(title)}</span></button>'
            f'<div class="skeleton embed-skeleton" aria-hidden="true"><span></span></div>'
            f'<figcaption><span class="embed-note">{esc(tr_fmt(t["embedNote"], provider=name))}</span>'
            f'<label class="embed-always"><input type="checkbox"> {esc(tr_fmt(t["embedAlways"], provider=name))}</label>'
            f'<a class="embed-link" href="{esc(watch)}" rel="noopener">{esc(tr_fmt(t["embedWatch"], provider=name))}</a></figcaption></figure>')


EMBED_RE = re.compile(r'<p class="embed">\s*<a\s+[^>]*?href="([^"]+)"[^>]*>(.*?)</a>\s*</p>', re.S)


def expand_embeds(body, lang):
    def one(m):
        title = plain(m.group(2), 200) or I18N[lang]["galleryVideo"]
        v = parse_video(m.group(1))
        if not v:
            UNKNOWN_EMBEDS.append(html.unescape(m.group(1)))
            return f'<p><a {href_attr(html.unescape(m.group(1)))}>{esc(title)}</a></p>'
        return embed_html(v[0], v[1], title, lang)
    return EMBED_RE.sub(one, body)


def _attrs(tag):
    return {k: v for k, v in re.findall(r'([\w:-]+)="([^"]*)"', tag)}


def _fix_img(m):
    tag = m.group(0)
    a = _attrs(tag)
    classes = a.get("class", "").split()
    if "ph-img" in classes and a.get("width") and a.get("loading"):
        return tag
    src = a.get("src")
    if not src:
        return tag
    s = html.unescape(src)
    wh = image_size(s) if s.startswith("/") else None
    w, h = a.get("width") or (wh and str(wh[0])), a.get("height") or (wh and str(wh[1]))
    srcset = ""
    if s.startswith("/media/") and not a.get("srcset") and (ss := auto_srcset(s)):
        srcset = f' srcset="{esc(ss)}" sizes="(max-width: 760px) 100vw, 760px"'
    elif a.get("srcset"):
        srcset = f' srcset="{a["srcset"]}"' + (f' sizes="{a["sizes"]}"' if a.get("sizes") else "")
    dims = f' width="{w}" height="{h}"' if w and h else ""
    cls = " ".join(dict.fromkeys(classes + ["ph-img"]))
    return f'<img src="{src}"{srcset} alt="{a.get("alt", "")}"{dims} loading="lazy" decoding="async" class="{cls}">'


PHOTO = r'(?:<figure><img [^>]+></figure>|<p><img [^>]+></p>|<img [^>]+>)'


def _photo_run(m, lang):
    cells = []
    for tag in re.findall(r"<img [^>]+>", m.group(0)):
        a = _attrs(tag)
        src = html.unescape(a.get("src", ""))
        wh = image_size(src) if src.startswith("/") else None
        data = f' data-w="{wh[0]}" data-h="{wh[1]}"' if wh else ""
        alt = a.get("alt", "")
        thumb = small_variant(src) or src
        cells.append(f'<a href="{esc(src)}"{data}{f" data-caption=" + chr(34) + alt + chr(34) if alt else ""} aria-label="{esc(I18N[lang]["photoOpen"])}">'
                     f'<img src="{esc(thumb)}" alt="{alt}"></a>')
    return '<div class="photo-run" data-lightbox>' + "".join(cells) + "</div>"


def _link(m):
    tag = m.group(0)
    a = _attrs(tag)
    if "rel" not in a and is_external(html.unescape(a.get("href", ""))):
        return tag[:-1] + ' rel="noopener">'
    return tag


def enhance_body(body, lang):
    """Embeds, layout-stable lazy images, photo grids that open in the lightbox, scrollable tables, safe external links."""
    body = re.sub(r"<(/?)h1(\s|>)", r"<\1h2\2", body)
    body = expand_embeds(body, lang)
    body = re.sub(rf"(?:{PHOTO}\s*){{2,}}", lambda m: _photo_run(m, lang), body)
    body = re.sub(r"<img [^>]+>", _fix_img, body)
    body = re.sub(r"<a\s[^>]*>", _link, body)
    body = body.replace("<table>", '<div class="table-wrap" tabindex="0"><table>')
    return body.replace("</table>", "</table></div>")


def note_media(body, owner):
    for u in re.findall(r'(?:src|href)="(/media/[^"]+)"', body or ""):
        if not local_exists(u):
            MISSING_MEDIA.add(u)


def gallery_html(items, lang, alt_default=""):
    if not items:
        return ""
    cells = []
    for g in items:
        src = g.get("src")
        if not src:
            continue
        full = image_size(src)
        data = f' data-w="{g.get("w") or (full and full[0]) or ""}" data-h="{g.get("h") or (full and full[1]) or ""}"'
        cap = g.get("caption") or ""
        thumb = small_variant(src) or src
        tw = image_size(thumb)
        dims = f' width="{tw[0]}" height="{tw[1]}"' if tw else ""
        cells.append(f'<li><a href="{esc(src)}"{data}{f" data-caption=" + chr(34) + esc(cap) + chr(34) if cap else ""}>'
                     f'<img class="ph-img" src="{esc(thumb)}" alt="{esc(g.get("alt") or cap or alt_default)}"{dims} loading="lazy" decoding="async"></a></li>')
    return f'<ul class="gallery" data-lightbox>{"".join(cells)}</ul>'


# ---------------------------------------------------------------- menus

MENU_KEYS = ("main", "footer", "social", "legal")


def resolve_link(u):
    if not u or is_external(u):
        return u
    seen = set()
    while u in REDIR_MAP and u not in seen:
        seen.add(u)
        u = REDIR_MAP[u]
    p = PAGES.get(u)
    return p["redirect"] if p and p.get("redirect") else u


def menu(lang, key):
    return (MENUS.get(lang) or {}).get(key) or []


def derive_main(lang):
    """Fallback main menu when menus.json has none: top-level pages (with their children) in page order."""
    kids = children_of(None, lang)
    return [{"title": p["title"], "url": p["url"], "children": [{"title": c["title"], "url": c["url"]} for c in children_of(p["url"], lang)]}
            for p in kids if p.get("src") != "(synthetic)" and not p.get("redirect")]


def main_menu(lang):
    return menu(lang, "main") or derive_main(lang)


def node_active(node, url):
    u = resolve_link(node.get("url"))
    if u and not is_external(u) and u not in HOME_URLS and (url == u or url.startswith(u)):
        return True
    return any(node_active(c, url) for c in node.get("children") or [])


def link_li(n, current):
    u = resolve_link(n.get("url"))
    cur = ' aria-current="page"' if u == current else ""
    return f'<li><a {href_attr(u)}{cur}>{esc(n["title"])}</a></li>'


def sub_html(node, lang, current):
    parts = []
    f = node.get("feature")
    if f and f.get("url"):
        im = img(f["image"], "", sizes="(max-width: 700px) 100vw, 320px") if f.get("image") else ""
        parts.append(f'<li class="sub-feature"><a {href_attr(resolve_link(f["url"]))}>{im}<b>{esc(f["title"])}</b>'
                     f'{f"<span>{esc(f["text"])}</span>" if f.get("text") else ""}</a></li>')
    for c in node.get("children") or []:
        kids = c.get("children") or []
        if kids:
            head = (f'<a {href_attr(resolve_link(c["url"]))}>{esc(c["title"])}</a>' if c.get("url") else esc(c["title"]))
            parts.append(f'<li class="sub-group"><span class="sub-heading">{head}</span><ul>{"".join(link_li(k, current) for k in kids)}</ul></li>')
        elif c.get("url"):
            parts.append(link_li(c, current))
    return "".join(parts)


def nav_html(lang, current):
    t = I18N[lang]
    home = home_url(lang)
    lis = [f'<li class="nav-home"><a href="{home}"{" aria-current=" + chr(34) + "page" + chr(34) if current == home else ""}>{esc(t["home"])}</a></li>']
    for n in main_menu(lang):
        u = resolve_link(n.get("url"))
        active = node_active({**n, "url": u}, current) if u or n.get("children") else False
        cur = ' aria-current="page"' if u == current else (' class="is-active"' if active else "")
        kids = bool(n.get("children")) or bool(n.get("feature"))
        label = f'<a {href_attr(u)}{cur}>{esc(n["title"])}</a>' if u else f'<span class="nav-heading">{esc(n["title"])}</span>'
        sub = ""
        if kids:
            sub = (f'<button class="sub-toggle" type="button" aria-expanded="false" aria-label="{esc(n["title"])}: {esc(t["morePages"])}">'
                   f'<span aria-hidden="true"></span></button><ul class="sub">{sub_html(n, lang, current)}</ul>')
        lis.append(f'<li{" class=" + chr(34) + "has-sub" + chr(34) if kids else ""}>{label}{sub}</li>')
    return f'<ul class="nav-list">{"".join(lis)}</ul>'


def footer_cols(lang):
    cols = []
    src = menu(lang, "footer") or [{"title": n["title"], "url": n.get("url"), "children": n.get("children")} for n in main_menu(lang)]
    for n in src:
        items = []
        for c in n.get("children") or []:
            if c.get("children") or not c.get("url"):
                items.append(f'<li><h3 class="f-heading">{esc(c["title"])}</h3></li>')
                items += [link_li(k, "") for k in c.get("children") or []]
            else:
                items.append(link_li(c, ""))
        u = resolve_link(n.get("url"))
        head = f'<a {href_attr(u)}>{esc(n["title"])}</a>' if u else esc(n["title"])
        cols.append(f'<div class="f-col"><h2>{head}</h2>{"<ul>" + "".join(items) + "</ul>" if items else ""}</div>')
    return "".join(cols)


def legal_links(lang):
    t = I18N[lang]
    links = [(l["title"], resolve_link(l["url"])) for l in menu(lang, "legal") if l.get("url")]
    if not links:
        links = [(p["title"], p["url"]) for p in ALL_PAGES if p["lang"] == lang and p.get("template") == "privacy"]
    links.append((t["gdpr"], sec("gdpr", lang)))
    app = next((p for p in ALL_PAGES if p["lang"] == lang and p.get("template") == "app"), None)
    if app:
        links.append((t["appLink"], app["url"]))
    return " · ".join(f'<a {href_attr(u)}>{esc(title)}</a>' for title, u in links)


def social_html(lang):
    items = menu(lang, "social") or menu(DEFAULT_LANG, "social") or SITE.get("social", [])
    return "".join(f'<a href="{esc(s["url"])}" rel="noopener">{esc(s["label"])}</a>' for s in items)


def lang_switch(lang, url, alt, section=None):
    out = []
    for l in LANGS:
        href = alt.get(l) if alt is not None and alt.get(l) else switch_target(lang, url, l, section)
        cur = ' aria-current="true"' if l == lang else ""
        out.append(f'<a href="{esc(href)}" lang="{l}" hreflang="{l}"{cur} title="{esc(I18N[l]["langName"])}">{l.upper()}</a>')
    return "".join(out)


# ---------------------------------------------------------------- layout

FONTS_PRELOAD = ["asap-latin-400-normal", "eb-garamond-latin-500-normal"]  # first-screen body and heading; latin-ext loads on demand
SCRIPT_KEYS = ["news", "pressReleases", "galleries", "galleryPhoto", "galleryAlbum", "galleryVideo", "publications", "inTheNews", "readMore", "page",
               "search", "searchLabel", "searchPlaceholder", "searchNone", "searchCount", "searchLoading", "searchFailed", "previous", "next",
               "embedNote", "embedAlways", "embedWatch", "embedPlay", "lightboxClose", "lightboxPrev", "lightboxNext", "lightboxOf", "archiveNote",
               "notFound", "gdprSending", "gdprSent", "gdprFailed", "gdprTooFast", "gdprNotSet", "date", "organisation", "language", "agency"]


def site_data(lang, archive_bases=None):
    email = SITE["contact"]["email"]
    t = {k: tr_fmt(I18N[lang][k], email=email) if "{email}" in I18N[lang][k] else I18N[lang][k] for k in SCRIPT_KEYS if k in I18N[lang]}
    data = {"lang": lang, "home": home_url(lang), "search": {"url": sec("search", lang), "index": f"/search/index.{lang}.json"},
            "archiveBases": archive_bases or [sec("news", lang), sec("press", lang), sec("galleries", lang)], "t": t}
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def og_base():
    return f"https://{os.environ['VERCEL_PROJECT_PRODUCTION_URL']}" if os.environ.get("VERCEL_PROJECT_PRODUCTION_URL") else SITE["baseUrl"]


def lockup_html(lang, names):
    f = STATIC / "img" / "lockup" / f"{lang}.svg"
    if f.exists():
        vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', f.read_text(encoding="utf-8")).group(1).split()]
        return (f'<img class="lockup" src="/img/lockup/{lang}.svg" alt="{esc(names["lockup"])}" width="{vb[2]:.0f}" height="{vb[3]:.0f}"'
                f' style="--h:{vb[3] / 126:.4f};--t:{vb[1] / 126:.4f}">')
    s = STATIC / "img" / "lockup" / "shield.svg"
    dims = ""
    if s.exists():
        vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', s.read_text(encoding="utf-8")).group(1).split()]
        dims = f' width="{vb[2]:.0f}" height="{vb[3]:.0f}"'
    return f'<img class="lockup lockup--shield" src="/img/lockup/shield.svg" alt=""{dims}><span class="lockup-text">{esc(names["lockup"])}</span>'


def pinned_html(lang):
    t = I18N[lang]
    return "".join(
        f'<aside class="pinned" aria-label="{esc(t["pinned"])}"><div class="wrap"><p><b>{esc(n["title"])}</b>'
        f'{" " + esc(n["excerpt"]) if n.get("excerpt") else ""} <a href="{n["url"]}">{esc(t["readMore"])}</a></p></div></aside>'
        for n in NEWS if n.get("pinned") and n["lang"] == lang)


def jsonld_org(lang, canonical):
    names = SITE["names"][lang]
    same = [s["url"] for s in (menu(lang, "social") or menu(DEFAULT_LANG, "social") or SITE.get("social", []))]
    data = {"@context": "https://schema.org", "@type": "Organization", "name": names["orderShort"], "alternateName": names["order"], "url": canonical}
    if same:
        data["sameAs"] = same
    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False).replace("<", "\\u003c") + "</script>"


def layout(*, lang, url, title, body, description="", image=None, status=None, alt=None, main_class="", hreflang=True, noindex=False,
           head_extra="", scripts=(), pinned=False, canonical=None, archive_bases=None, tail="", section=None):
    t, names = I18N[lang], SITE["names"][lang]
    full_title = f"{title} | {names['site']}" if title != names["site"] else title
    canonical = canonical or SITE["baseUrl"] + url
    alt = alt if alt is not None else alts_for(url)
    desc = plain(description, 300) or plain(body, 160) or f"{title} – {names['orderShort']}"
    og_img = ""
    if image and image.startswith("/media/") and local_exists(image):
        og_img = f'<meta property="og:image" content="{og_base()}{esc(image)}">'
    elif (STATIC / "img" / f"og-{lang}.jpg").exists():
        og_img = (f'<meta property="og:image" content="{og_base()}/img/og-{lang}.jpg"><meta property="og:image:width" content="1200">'
                  f'<meta property="og:image:height" content="630"><meta property="og:image:alt" content="{esc(names["lockup"])}">')
    robots = '<meta name="robots" content="noindex, nofollow">' if (noindex or not PRODUCTION) else ""
    alt_tags = "".join(f'<link rel="alternate" hreflang="{l}" href="{SITE["baseUrl"]}{esc(u)}">' for l, u in alt_links(alt).items()) if hreflang else ""
    preload = "".join(f'<link rel="preload" href="/fonts/{f}.woff2" as="font" type="font/woff2" crossorigin>' for f in FONTS_PRELOAD) + \
        '<link rel="preload" href="/img/banner/banner-photo.webp" as="image" fetchpriority="high">'
    ld = jsonld_org(lang, canonical) if url == home_url(lang) else ""
    status_bar = ""
    if status and not PRODUCTION:
        status_bar = f'<p class="content-status content-status--{esc(status)}"><span>{esc(t["status"].get(status, status))}</span></p>'
    c = SITE["contact"]
    credits = (MENUS.get(lang) or {}).get("footerCredits") or (MENUS.get(DEFAULT_LANG) or {}).get("footerCredits") or {}
    f_name = credits.get("name") or names["order"]
    f_addr = credits.get("address") or c["address"]
    f_phone = credits.get("phone") or c["phone"]
    f_mail = credits.get("email") or c["email"]
    script_tags = "".join(f'<script src="{s}?v={ASSET_VERSION}" defer></script>' for s in scripts)
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(desc)}">
{robots}
<link rel="canonical" href="{esc(canonical)}">
{alt_tags}
<meta property="og:type" content="website">
<meta property="og:site_name" content="{esc(names['site'])}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{esc(canonical)}">
{og_img}
<meta property="og:locale" content="{LOCALES.get(lang, lang)}">
<meta name="twitter:card" content="summary_large_image">
{ld}
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="/img/favicon/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/img/favicon/favicon-16x16.png">
<link rel="apple-touch-icon" href="/img/favicon/apple-touch-icon-180x180.png">
<link rel="alternate" type="application/rss+xml" title="{esc(names['site'])}" href="{sec('feed', lang)}">
{preload}
<script type="application/json" id="site-data">{site_data(lang, archive_bases)}</script>
<link rel="stylesheet" href="/css/site.css?v={ASSET_VERSION}">
<script src="/js/head.js?v={ASSET_VERSION}"></script>
<script src="/js/site.js?v={ASSET_VERSION}" defer></script>
{head_extra}
</head>
<body>
<a class="skip" href="#main">{esc(t['skip'])}</a>
<header class="site-header">
 <div class="topbar"><div class="wrap">
  <a class="topbar-home" href="{home_url(lang)}">{esc(names['orderActivities'])}</a>
  <span class="topbar-social">{social_html(lang)}</span>
  <form class="site-search" role="search" action="{sec('search', lang)}" method="get"><label class="visually-hidden" for="site-q">{esc(t['searchLabel'])}</label><input id="site-q" type="search" name="q" autocomplete="off" placeholder="{esc(t['searchPlaceholder'])}"><button type="submit" aria-label="{esc(t['search'])}"></button></form>
  <nav class="lang" aria-label="{esc(t['langLabel'])}">{lang_switch(lang, url, alt, section)}</nav>
 </div></div>
 <div class="banner"><div class="wrap">
  <a class="banner-home" href="{home_url(lang)}">{lockup_html(lang, names)}</a>
  <p class="fullname">{esc(names['order'])}</p>
 </div></div>
 <nav class="mainnav" aria-label="{esc(t['menu'])}"><div class="wrap">
  <button class="menu-toggle" type="button" aria-expanded="false" aria-controls="menu">{esc(t['menu'])}</button>
  <div id="menu" class="menu">{nav_html(lang, url)}</div>
 </div></nav>
</header>
<main id="main" class="{main_class}" tabindex="-1">
{pinned_html(lang) if pinned else ""}
{status_bar}
{body}
</main>
<footer class="site-footer">
 <div class="f-nav"><div class="wrap">{footer_cols(lang)}</div></div>
 <div class="f-id"><div class="wrap">
  <p class="f-name">{esc(f_name)}</p>
  <p>{esc(f_addr)} · <a href="tel:{esc(re.sub(r'[^0-9+]', '', f_phone))}">{esc(f_phone)}</a> · <a href="mailto:{esc(f_mail)}">{esc(f_mail)}</a></p>
 </div></div>
 <div class="f-red"><div class="wrap">
  <p>{legal_links(lang)}</p>
 </div></div>
</footer>
{tail}{script_tags}
</body>
</html>
"""


# ---------------------------------------------------------------- page tree

PAGE_CHILDREN = {}
for _p in ALL_PAGES:
    PAGE_CHILDREN.setdefault((_p["lang"], _p.get("parent")), []).append(_p)
for _k in PAGE_CHILDREN:
    PAGE_CHILDREN[_k].sort(key=lambda p: (p.get("order") or 0, p["title"]))


def children_of(url, lang):
    return [p for p in PAGE_CHILDREN.get((lang, url), []) if p.get("template") != "home" and p["url"] != home_url(lang)]


def page_trail(p):
    trail, seen, cur = [], {p["url"]}, p
    while cur.get("parent") and cur["parent"] in PAGES and cur["parent"] not in seen:
        cur = PAGES[cur["parent"]]
        seen.add(cur["url"])
        trail.insert(0, (cur["title"], cur["url"]))
    return trail


def crumbs_html(trail, lang):
    """trail: [(title, url)] below the home page; the last entry is the current page."""
    if not trail:
        return ""
    items = [f'<li><a href="{home_url(lang)}">{esc(I18N[lang]["home"])}</a></li>']
    for i, (title, u) in enumerate(trail):
        last = i == len(trail) - 1
        items.append(f'<li>{"<span aria-current=" + chr(34) + "page" + chr(34) + ">" + esc(title) + "</span>" if last else f"<a href={chr(34)}{esc(u)}{chr(34)}>{esc(title)}</a>"}</li>')
    return f'<nav class="crumbs" aria-label="{esc(I18N[lang]["breadcrumb"])}"><ol>{"".join(items)}</ol></nav>'


def side_nav(p):
    lang = p["lang"]
    top = p
    seen = {p["url"]}
    while top.get("parent") and top["parent"] in PAGES and top["parent"] not in seen:
        top = PAGES[top["parent"]]
        seen.add(top["url"])
    if top["url"] == p["url"] or not children_of(top["url"], lang):
        return ""
    ancestors = {u for _, u in page_trail(p)}

    def walk(parent_url):
        out = []
        for c in children_of(parent_url, lang):
            cur = ' aria-current="page"' if c["url"] == p["url"] else ""
            sub = walk(c["url"]) if (c["url"] == p["url"] or c["url"] in ancestors) and children_of(c["url"], lang) else ""
            out.append(f'<li><a {href_attr(c.get("redirect") or c["url"])}{cur}>{esc(c["title"])}</a>{sub}</li>')
        return f'<ul>{"".join(out)}</ul>'
    return (f'<nav class="side-nav" aria-label="{esc(I18N[lang]["inSection"])}"><p class="label">'
            f'<a href="{top["url"]}">{esc(top["title"])}</a></p>{walk(top["url"])}</nav>')


def section_children_html(p):
    kids = children_of(p["url"], p["lang"])
    if not kids or 'class="cards"' in p["body"]:
        return ""
    items = []
    for k in kids:
        desc = k.get("description") or plain(k.get("body", ""), 150)
        items.append(f'<li><a {href_attr(k.get("redirect") or k["url"])}><b>{esc(k["title"])}</b>{f"<span>{esc(desc)}</span>" if desc else ""}</a></li>')
    return f'<ul class="index-list">{"".join(items)}</ul>'


# ---------------------------------------------------------------- cards and pagination


def card_html(kind, *, lang, url=None, title, image=None, alt="", date=None, date_label=None, kind_label=None, extra_meta=(), text="",
              files=None, h=2, sizes="(max-width: 640px) 100vw, (max-width: 1000px) 50vw, 33vw", external=False):
    link = f'href="{esc(url)}"' + (' rel="noopener"' if external else "") if url else ""
    media = ""
    if image:
        im = img(image, alt, sizes=sizes)
        media = f'<a class="card-media" {link} tabindex="-1" aria-hidden="true">{im}</a>' if url else f'<div class="card-media">{im}</div>'
    meta = []
    if date:
        meta.append(f'<time datetime="{esc(str(date)[:10] if len(str(date)) > 7 else date)}">{esc(date_label or fmt_date(date, lang))}</time>')
    if kind_label:
        meta.append(f'<span class="card-kind">{esc(kind_label)}</span>')
    meta += [f'<span>{esc(m)}</span>' for m in extra_meta if m]
    meta_html = f'<p class="card-meta">{"".join(meta)}</p>' if meta else ""
    heading = f'<a {link}>{esc(title)}</a>' if url else esc(title)
    file_html = ""
    if files:
        file_html = '<ul class="card-files">' + "".join(f'<li><a {href_attr(f["url"])}>{esc(f.get("label") or I18N[lang]["files"])}</a></li>' for f in files) + "</ul>"
    return (f'<li class="card card--{kind}">{media}<div class="card-body">{meta_html}<h{h} class="card-title">{heading}</h{h}>'
            f'{f"<p class=" + chr(34) + "card-text" + chr(34) + ">" + esc(text) + "</p>" if text else ""}{file_html}</div></li>')


def video_poster(item):
    v = parse_video(item.get("video") or "")
    if v and v[0] == "youtube" and local_exists(f"/media/embeds/youtube-{v[1]}.webp"):
        return f"/media/embeds/youtube-{v[1]}.webp"
    return None


def item_image(item):
    if item.get("image"):
        return item["image"]
    g = item.get("gallery") or []
    if g and g[0].get("src"):
        return g[0]["src"]
    return video_poster(item)


def news_card(n, lang, h=2):
    return card_html("news", lang=lang, url=n["url"], title=n["title"], image=n.get("image"), alt=n.get("imageAlt", ""), date=n["date"][:10],
                     text=n.get("excerpt") or plain(n["body"], 200), h=h)


def press_card(n, lang, h=2):
    return card_html("press", lang=lang, url=n["url"], title=n["title"], date=n["date"][:10], extra_meta=[n.get("organisation")],
                     text=n.get("excerpt") or plain(n["body"], 200), h=h)


def gallery_card(n, lang, h=2):
    label = {"photo": "galleryPhoto", "album": "galleryAlbum", "video": "galleryVideo"}.get(n.get("kind"))
    return card_html("gallery", lang=lang, url=n["url"], title=n["title"], image=item_image(n), alt=n.get("imageAlt", ""), date=n["date"][:10],
                     kind_label=I18N[lang][label] if label else None, h=h)


def page_card(p, lang, h=3, kind_label=None, text=None):
    return card_html("page", lang=lang, url=p.get("redirect") or p["url"], title=p["title"], image=p.get("image"), alt=p.get("imageAlt", ""),
                     kind_label=kind_label, text=text if text is not None else (p.get("description") or plain(p.get("body", ""), 160)), h=h,
                     external=is_external(p.get("redirect") or ""))


def publication_card(it, lang, h=2):
    return card_html("publication", lang=lang, title=it["title"], image=it.get("image"), date=it.get("date"), date_label=it.get("dateLabel"),
                     files=it.get("files"), h=h)


def cutting_card(it, lang, h=2):
    return card_html("cutting", lang=lang, url=it["url"], title=it["title"], date=it.get("date"), extra_meta=[it.get("agency"), it.get("language")],
                     text=it.get("excerpt", ""), h=h, external=True)


def grid(cards, lang, text=False, side=False):
    if not cards:
        return f'<p class="empty">{esc(I18N[lang]["empty"])}</p>'
    cls = "card-grid" + (" card-grid--text" if text else "") + (" card-grid--side" if side else "")
    return f'<ol class="{cls}">{"".join(cards)}</ol>'


def pager_html(base, page_no, n_pages, lang):
    if n_pages <= 1:
        return ""
    t = I18N[lang]
    shown = sorted({1, n_pages, page_no - 1, page_no, page_no + 1} & set(range(1, n_pages + 1)))
    lis, last = [], 0
    for n in shown:
        if n - last > 1:
            lis.append('<li class="pager-gap">…</li>')
        cur = ' aria-current="page"' if n == page_no else ""
        lis.append(f'<li><a href="{page_url(base, n)}"{cur} aria-label="{esc(tr_fmt(t["page"], n=n))}">{n}</a></li>')
        last = n
    prev = f'<a class="pager-prev" rel="prev" href="{page_url(base, page_no - 1)}">{esc(t["previous"])}</a>' if page_no > 1 else ""
    nxt = f'<a class="pager-next" rel="next" href="{page_url(base, page_no + 1)}">{esc(t["next"])}</a>' if page_no < n_pages else ""
    return f'<nav class="pager" aria-label="{esc(t["pagerLabel"])}">{prev}<ol>{"".join(lis)}</ol>{nxt}</nav>'


def tabs_html(links, label):
    """links: [(title, url, current)]"""
    return f'<nav class="tabs" aria-label="{esc(label)}">' + "".join(
        f'<a href="{esc(u)}"{" aria-current=" + chr(34) + "page" + chr(34) if cur else ""}>{esc(t)}</a>' for t, u, cur in links) + "</nav>"


def n_pages_of(items):
    return max(1, math.ceil(len(items) / PER_PAGE))


def chunk(items, page_no):
    return items[(page_no - 1) * PER_PAGE: page_no * PER_PAGE]


def page_suffix(title, page_no, lang):
    return title if page_no == 1 else f"{title} – {tr_fmt(I18N[lang]['page'], n=page_no)}"


# ---------------------------------------------------------------- output registry

WRITTEN = {}
SITEMAP = []  # (url, alt)


def write(url, html_text, *, sitemap=False, alt=None):
    if url in WRITTEN:
        warn(f"url written twice: {url}")
    WRITTEN[url] = True
    path = DIST / url.lstrip("/") / "index.html" if url.endswith("/") else DIST / url.lstrip("/")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_text, encoding="utf-8")
    if sitemap:
        SITEMAP.append((url, alt if alt is not None else alts_for(url)))


# ---------------------------------------------------------------- listings


def listing_doc(lang, *, base, page_no, n_pages, title, trail, cards_html, intro="", tabs="", years="", main_class="", alt=None, description="",
                lead_html="", pinned=False, section=None):
    t = I18N[lang]
    url = page_url(base, page_no)
    full = page_suffix(title, page_no, lang)
    body = f"""
<div class="wrap">{crumbs_html(trail, lang)}</div>
<div class="wrap page page--listing">
 <header class="page-head"><h1 class="display">{esc(title)}</h1>{lead_html}</header>
 {intro}
 {tabs}
 {years}
 {cards_html}
 {pager_html(base, page_no, n_pages, lang)}
</div>"""
    return layout(lang=lang, url=url, title=full, body=body, description=description or f"{full} – {SITE['names'][lang]['orderShort']}",
                  alt=alt, hreflang=page_no == 1, main_class=main_class, pinned=pinned, section=section)


def write_listing(lang, base, items, make_card, *, title, trail, text=False, intro="", tabs="", years="", alt=None, description="", sitemap=True,
                  pinned=False, main_class="", section=None):
    n = n_pages_of(items)
    for i in range(1, n + 1):
        cards = grid([make_card(x, lang) for x in chunk(items, i)], lang, text=text)
        doc = listing_doc(lang, base=base, page_no=i, n_pages=n, title=title, trail=trail, cards_html=cards, intro=intro if i == 1 else "", tabs=tabs,
                          years=years, alt=alt, description=description, pinned=pinned and i == 1, main_class=main_class, section=section)
        write(page_url(base, i), doc, sitemap=sitemap and i == 1, alt=alt)


YEARS = {l: {n["date"][:4] for n in by_lang(NEWS, l)} for l in LANGS}


def render_news(lang):
    t = I18N[lang]
    items = by_lang(NEWS, lang)
    base = sec("news", lang)
    intro_page = PAGES.get(base)
    title = (intro_page or {}).get("title") or t["news"]
    years = sorted({n["date"][:4] for n in items}, reverse=True)

    def tabs(active_key=None):
        links = [(t["allCategories"], base, active_key is None)]
        for k in SITE.get("newsFilters", []):
            u = cat_url(k, lang)
            if u:
                links.append((cat_name(k, lang), u, active_key == k))
        return tabs_html(links, t["category"]) if len(links) > 1 else ""

    def year_nav(active=None):
        if not years:
            return ""
        return (f'<nav class="years" aria-label="{esc(t["newsArchive"])}">' + "".join(
            f'<a href="{base}{y}/"{" aria-current=" + chr(34) + "page" + chr(34) if y == active else ""}>{y}</a>' for y in years) + "</nav>")

    news_alt = section_alt("news")
    write_listing(lang, base, items, news_card, title=title, trail=[(title, base)], tabs=tabs(), years=year_nav(), alt=news_alt,
                  description=f"{title} – {SITE['names'][lang]['orderShort']}", pinned=True, main_class="news-index", section="news",
                  intro=f'<div class="prose">{enhance_body(intro_page["body"], lang)}</div>' if intro_page and intro_page.get("body") else "")
    for key, v in CATS.items():  # one archive per category term of this language
        u = cat_url(key, lang)
        if not u or u == base:
            continue
        group = {l: cat_url(key, l) for l in LANGS if cat_url(key, l)}
        name = cat_name(key, lang)
        write_listing(lang, u, cat_members(key, items), news_card, title=name, trail=[(title, base), (name, u)], tabs=tabs(key), years=year_nav(), alt=group,
                      description=f"{name} – {title}", section="news")
    for y in years:
        yi = [n for n in items if n["date"].startswith(y)]
        yt = f"{title} {y}"
        group = {l: f"{sec('news', l)}{y}/" for l in LANGS if y in YEARS[l]}
        write_listing(lang, f"{base}{y}/", yi, news_card, title=yt, trail=[(title, base), (y, f"{base}{y}/")], tabs=tabs(), years=year_nav(y), alt=group,
                      description=f"{yt} – {SITE['names'][lang]['orderShort']}", section="news")


GALLERY_KINDS = [("photo", "galleryPhoto"), ("album", "galleryAlbum"), ("video", "galleryVideo")]


def gallery_type_url(kind, lang):
    slug = (SITE.get("galleryTypes", {}).get(kind) or {}).get(lang)
    return f"{sec('galleryTypes', lang)}{slug}/" if slug else None


def render_galleries(lang):
    t = I18N[lang]
    items = by_lang(GALLERIES, lang)
    base = sec("galleries", lang)
    intro_page = PAGES.get(base)
    title = (intro_page or {}).get("title") or t["galleries"]

    def tabs(active=None):
        links = [(t["allCategories"], base, active is None)]
        links += [(t[label], gallery_type_url(k, lang), active == k) for k, label in GALLERY_KINDS if gallery_type_url(k, lang)]
        return tabs_html(links, t["category"])

    write_listing(lang, base, items, gallery_card, title=title, trail=[(title, base)], tabs=tabs(), alt=section_alt("galleries"),
                  description=f"{title} – {SITE['names'][lang]['orderShort']}", main_class="galleries-index", section="galleries",
                  intro=f'<div class="prose">{enhance_body(intro_page["body"], lang)}</div>' if intro_page and intro_page.get("body") else "")
    for k, label in GALLERY_KINDS:
        u = gallery_type_url(k, lang)
        if not u:
            continue
        group = {l: gallery_type_url(k, l) for l in LANGS if gallery_type_url(k, l)}
        write_listing(lang, u, [g for g in items if g.get("kind") == k], gallery_card, title=t[label], trail=[(title, base), (t[label], u)], tabs=tabs(k),
                      alt=group, description=f"{t[label]} – {title}", section="galleries")


# ---------------------------------------------------------------- singles


def related_news(lang, exclude, limit=3):
    return [n for n in by_lang(NEWS, lang) if n["url"] != exclude][:limit]


def related_aside(lang, news):
    if not news:
        return ""
    return (f'<aside class="related"><h2>{esc(I18N[lang]["latestNews"])}</h2>'
            f'{grid([news_card(n, lang, h=3) for n in news], lang)}</aside>')


def render_single(it, siblings, section_key):
    """News item, press release or gallery as an <article>."""
    lang, typ, t = it["lang"], it["type"], I18N[it["lang"]]
    idx = next((i for i, x in enumerate(siblings) if x["url"] == it["url"]), None)
    older = siblings[idx + 1] if idx is not None and idx + 1 < len(siblings) else None
    newer = siblings[idx - 1] if idx else None
    listing = sec(section_key, lang)
    listing_title = (PAGES.get(listing) or {}).get("title") or {"news": t["news"], "press": t["pressReleases"], "gallery": t["galleries"]}[typ]
    cover = ""
    if it.get("image"):
        cap = f'<figcaption>{esc(it["imageCredit"])}</figcaption>' if it.get("imageCredit") else ""
        cover = f'<figure class="article-cover">{img(it["image"], it.get("imageAlt", ""), eager=True, sizes="(max-width: 1100px) 100vw, 1100px")}{cap}</figure>'
    meta = f'<time datetime="{it["date"][:10]}">{esc(fmt_date(it["date"], lang))}</time>'
    if it.get("organisation"):
        meta += f' · {esc(it["organisation"])}'
    video = ""
    v = parse_video(it.get("video") or "")
    if v:
        video = embed_html(v[0], v[1], it["title"], lang)
    elif it.get("video"):
        UNKNOWN_EMBEDS.append(it["video"])
        video = f'<p><a {href_attr(it["video"])}>{esc(it["title"])}</a></p>'
    gal = gallery_html(it.get("gallery"), lang, it["title"])
    body_html = enhance_body(it["body"], lang)
    kind = it.get("kind")
    media_first = typ == "gallery"
    gallery_block = ""
    if gal:
        gallery_block = gal if media_first else f'<section class="article-gallery"><h2>{esc(t["galleryHeading"])}</h2>{gal}</section>'
    tags = ""
    if typ == "news":
        keys = [k for k in it.get("categories") or [] if cat_url(k, lang)]
        non_root = [k for k in keys if (CATS.get(k) or {}).get("parent")]
        keys = non_root or keys
        if keys:
            tags = '<ul class="tag-list">' + "".join(f'<li><a href="{cat_url(k, lang)}">{esc(cat_name(k, lang))}</a></li>' for k in keys) + "</ul>"
    nav = ""
    if older or newer:
        nav = (f'<nav class="article-nav" aria-label="{esc(t["pagerLabel"])}">'
               + (f'<a class="article-nav-prev" rel="prev" href="{older["url"]}"><span>{esc(t["previous"])}</span>{esc(older["title"])}</a>' if older else "")
               + (f'<a class="article-nav-next" rel="next" href="{newer["url"]}"><span>{esc(t["next"])}</span>{esc(newer["title"])}</a>' if newer else "") + "</nav>")
    main_media = ""
    if media_first:
        main_media = (video if kind == "video" else "") + gallery_block
        gallery_block = ""
        if kind != "video":
            video_after = video
        else:
            video_after = ""
    else:
        video_after = video
    body = f"""
<div class="wrap">{crumbs_html([(listing_title, listing), (it["title"], it["url"])], lang)}</div>
<article class="wrap page article article--{typ}">
 <header class="page-head">
  <p class="kicker"><a href="{listing}">{esc(listing_title)}</a></p>
  <h1 class="display">{esc(it["title"])}</h1>
  {f'<p class="subtitle">{esc(it["subtitle"])}</p>' if it.get("subtitle") else ""}
  <p class="article-meta">{meta}</p>
 </header>
 <div class="page-main">
  {cover}
  {main_media}
  <div class="prose">{body_html}</div>
  {video_after}
  {gallery_block}
  {tags}
  {nav}
 </div>
</article>
<div class="wrap">{related_aside(lang, related_news(lang, it["url"]))}</div>"""
    desc = it.get("excerpt") or plain(it["body"], 200)
    return layout(lang=lang, url=it["url"], title=it["title"], body=body, description=desc, image=it.get("image") or item_image(it), status=it.get("status"))


# ---------------------------------------------------------------- pages


def contacts_tabs(body, lang):
    regions = re.findall(r'<section class="region" id="([^"]+)">\s*<h2[^>]*>(.*?)</h2>', body, re.S)
    if len(regions) < 2:
        return ""
    return tabs_html([(plain(h, 80), f"#{i}", False) for i, h in regions], I18N[lang]["contact"])


def collection_filter(lang, name, cat_key=None):
    c = COLL[lang].get(name) or {}
    items = c.get("items") or []
    if cat_key:
        items = [i for i in items if i.get("category") == cat_key]
    return c, items


def pub_tabs(lang, coll, active=None):
    cats = coll.get("categories") or []
    if not cats:
        return ""
    links = [(I18N[lang]["allCategories"], coll["url"], active is None)] + [(c["title"], c["url"], active == c["key"]) for c in cats if safe_url(c.get("url", ""))]
    return tabs_html(links, I18N[lang]["category"])


def hub_html(p):
    lang, t = p["lang"], I18N[p["lang"]]
    blocks = []
    pc, pubs = collection_filter(lang, "publications")
    nc, cuts = collection_filter(lang, "in-the-news")
    press = by_lang(PRESS, lang)[:6]
    for title, link, items, make, text in ((t["publications"], pc.get("url"), pubs[:3], publication_card, False),
                                           (t["inTheNews"], nc.get("url"), cuts[:3], cutting_card, True),
                                           (t["pressReleases"], sec("pressList", lang), press, press_card, True)):
        if not items:
            continue
        more = f'<p><a class="link-strong" href="{link}">{esc(t["readMore"])}</a></p>' if link else ""
        blocks.append(f'<section class="hub-block"><h2>{esc(title)}</h2>{grid([make(i, lang, 3) for i in items], lang, text=text)}{more}</section>')
    return "".join(blocks)


def render_page(p, page_no=1):
    lang, url, t = p["lang"], p["url"], I18N[p["lang"]]
    tpl = p.get("template") or "default"
    body = enhance_body(p["body"], lang) if p["body"] else ""
    note_media(p["body"], url)
    figure = ""
    if p.get("image") and page_no == 1:
        cap = f'<figcaption>{esc(p["imageCredit"])}</figcaption>' if p.get("imageCredit") else ""
        figure = f'<figure class="page-figure">{img(p["image"], p.get("imageAlt", ""), eager=True, sizes="(max-width: 1100px) 100vw, 1100px")}{cap}</figure>'
    extra, n_pages, base = "", 1, url
    if tpl == "contacts":
        extra = contacts_tabs(p["body"], lang)
    elif tpl == "press-hub":
        extra = hub_html(p)
    elif tpl == "press-releases":
        items = by_lang(PRESS, lang)
        n_pages = n_pages_of(items)
        extra = grid([press_card(x, lang) for x in chunk(items, page_no)], lang, text=True)
    elif tpl == "publications":
        c, items = collection_filter(lang, "publications")
        n_pages = n_pages_of(items)
        extra = pub_tabs(lang, c) + grid([publication_card(x, lang) for x in chunk(items, page_no)], lang)
    elif tpl == "in-the-news":
        c, items = collection_filter(lang, "in-the-news")
        n_pages = n_pages_of(items)
        extra = grid([cutting_card(x, lang) for x in chunk(items, page_no)], lang, text=True)
    pager = pager_html(base, page_no, n_pages, lang)
    side = side_nav(p)
    children = section_children_html(p) if tpl == "default" else ""
    related = ""
    cards = [PAGES[u] for u in p.get("related") or [] if u in PAGES and PAGES[u]["lang"] == lang]
    if cards:
        related = f'<aside class="related"><h2>{esc(t["related"])}</h2>{grid([page_card(c, lang, h=3) for c in cards], lang, side=True)}</aside>'
    pt = page_suffix(p["title"], page_no, lang)
    trail = page_trail(p) + [(p["title"], url)]
    scripts = []
    html_body = f"""
<div class="wrap">{crumbs_html(trail, lang)}</div>
<article class="wrap page page--{tpl}{' page--with-side' if side else ''}">
 <header class="page-head">
  <h1 class="display">{esc(p['title'])}</h1>
 </header>
 <div class="page-main">
  {figure}
  {f'<div class="prose">{body}</div>' if body and page_no == 1 else ''}
  {extra}
  {pager}
  {children if page_no == 1 else ''}
  {related if page_no == 1 else ''}
 </div>
 {f'<div class="page-side">{side}</div>' if side else ''}
</article>"""
    return layout(lang=lang, url=page_url(url, page_no), title=pt, body=html_body, description=p.get("description", "") or plain(p["body"], 160) or f"{pt} – {SITE['names'][lang]['orderShort']}",
                  image=p.get("image"), status=p.get("status"), alt=alts_for(url), hreflang=page_no == 1, scripts=scripts)


def render_redirect_stub(url, target, title, lang):
    canonical = target if is_external(target) or target.startswith("http") else SITE["baseUrl"] + target
    t = I18N[lang]
    body = (f'<div class="wrap page page--simple"><header class="page-head"><h1 class="display">{esc(title)}</h1></header>'
            f'<div class="prose"><p>{esc(t["redirecting"])} <a {href_attr(target)}>{esc(target)}</a></p></div></div>')
    return layout(lang=lang, url=url, title=title, body=body, description=f"{t['redirecting']} {target}", noindex=True, canonical=canonical, alt={}, hreflang=False,
                  head_extra=f'<meta http-equiv="refresh" content="0;url={esc(target)}">')


def lang_of_path(path):
    m = re.match(r"^/(it|fr|de|es)/", path)
    return m.group(1) if m and m.group(1) in LANGS else DEFAULT_LANG


# ---------------------------------------------------------------- home


def home_feature(lang, items):
    t = I18N[lang]
    if not items:
        return ""

    def summary(n):
        txt = n.get("excerpt") or plain(n["body"], 190)
        return txt if len(txt) <= 190 else txt[:190].rsplit(" ", 1)[0] + "…"

    def cat(n):
        keys = [k for k in n.get("categories") or [] if (CATS.get(k) or {}).get("parent")] or (n.get("categories") or [])
        return cat_name(keys[0], lang) if keys and cat_term(keys[0], lang) else ""
    slides = "".join(
        f'<li class="hf-slide{" has-img" if n.get("image") else ""}" id="hf-{i}" aria-label="{i + 1} / {len(items)}">'
        f'{"<a class=" + chr(34) + "hf-media" + chr(34) + " href=" + chr(34) + n["url"] + chr(34) + " tabindex=" + chr(34) + "-1" + chr(34) + " aria-hidden=" + chr(34) + "true" + chr(34) + ">" + img(n["image"], "", sizes="(max-width: 700px) 0px, 480px", eager=i == 0) + "</a>" if n.get("image") else ""}'
        f'<div class="hf-text"><p class="hf-meta"><time datetime="{n["date"][:10]}">{esc(fmt_date(n["date"], lang))}</time>{f"<span>{esc(cat(n))}</span>" if cat(n) else ""}</p>'
        f'<h3><a href="{n["url"]}">{esc(n["title"])}</a></h3><p class="hf-sum">{esc(summary(n))}</p></div></li>' for i, n in enumerate(items))
    dots = "".join(f'<li><button type="button" aria-controls="hf-{i}" aria-label="{esc(n["title"])}"{" aria-current=" + chr(34) + "true" + chr(34) if i == 0 else ""}><span></span></button></li>'
                   for i, n in enumerate(items))
    return f"""<section class="home-feature" aria-labelledby="hf-tab-news"><div class="hf-tabs" role="tablist"><button type="button" role="tab" id="hf-tab-news" aria-controls="hf-news" aria-selected="true">{esc(t["news"])}</button></div>
  <div class="hf-panel" id="hf-news" role="tabpanel" aria-labelledby="hf-tab-news">
   <div class="hf-viewport"><ol class="hf-track">{slides}</ol></div>
   <div class="hf-nav"><button type="button" class="hf-step" data-step="-1" aria-label="{esc(t["previous"])}"><span aria-hidden="true">↑</span></button><ol class="hf-dots">{dots}</ol><button type="button" class="hf-step" data-step="1" aria-label="{esc(t["next"])}"><span aria-hidden="true">↓</span></button></div>
   <p class="hf-all"><a class="link-strong" href="{sec("news", lang)}">{esc(t["allNews"])}</a></p>
  </div>
 </section>"""


def _section(cls, title, inner, tid):
    return f'<section class="{cls}" aria-labelledby="{tid}"><h2 id="{tid}" class="display-s">{esc(title)}</h2>{inner}</section>' if inner else ""


def render_home(lang):
    t, names = I18N[lang], SITE["names"][lang]
    page = PAGES.get(home_url(lang)) or {}
    h = page.get("home") or {}
    head = h.get("headings") or {}
    news = by_lang(NEWS, lang)
    parts = [f'<h1 class="visually-hidden">{esc(names["site"])}</h1>', home_feature(lang, news[:5])]
    works = h.get("works") or {}
    if works.get("items"):
        lis = "".join(f'<li><a {href_attr(resolve_link(i["url"]))}>{img(i["icon"], "", cls="works-icon", sizes="64px") if i.get("icon") else ""}<b>{esc(i["title"])}</b></a></li>'
                      for i in works["items"])
        parts.append(_section("home-works", works.get("title", ""), f'<ul class="works">{lis}</ul>', "hw-title"))
    if news:
        parts.append(f'<section class="home-news" aria-labelledby="hn-title"><div class="section-head"><h2 id="hn-title" class="display-s">{esc(head.get("latestNews") or t["latestNews"])}</h2>'
                     f'<a class="link-strong" href="{sec("news", lang)}">{esc(t["allNews"])}</a></div>{grid([news_card(n, lang, 3) for n in news[:6]], lang)}</section>')
    orgs = h.get("organisations") or {}
    if orgs.get("items"):
        cards = "".join(card_html("page", lang=lang, url=resolve_link(i["url"]), title=i["title"], image=i.get("image"), h=3, external=is_external(i["url"])) for i in orgs["items"][:4])
        parts.append(_section("home-orgs", orgs.get("title", ""), f'<ol class="card-grid">{cards}</ol>', "ho-title"))
    mp = h.get("map") or {}
    if mp.get("image"):
        link = mp.get("link") or {}
        parts.append(f'<section class="home-map" aria-labelledby="hm-title"><h2 id="hm-title" class="display-s">{esc(mp.get("title", ""))}</h2>'
                     f'<figure>{img(mp["image"], mp.get("title", ""), sizes="(max-width: 1100px) 100vw, 1100px")}</figure>'
                     f'{f"<p><a class=" + chr(34) + "btn" + chr(34) + " " + href_attr(resolve_link(link["url"])) + ">" + esc(link["title"]) + "</a></p>" if link.get("url") else ""}</section>')
    gals = by_lang(GALLERIES, lang)[:6]
    if gals:
        parts.append(f'<section class="home-galleries" aria-labelledby="hg-title"><div class="section-head"><h2 id="hg-title" class="display-s">{esc(head.get("galleries") or t["galleries"])}</h2>'
                     f'<a class="link-strong" href="{sec("galleries", lang)}">{esc(t["allGalleries"])}</a></div>{grid([gallery_card(g, lang, 3) for g in gals], lang)}</section>')
    feats = h.get("features") or []
    if feats:
        cards = "".join(card_html("page", lang=lang, url=resolve_link(f["url"]), title=f["title"], image=f.get("image"), kind_label=f.get("heading"), text=f.get("text", ""), h=3,
                                  external=is_external(f["url"])) for f in feats[:3])
        parts.append(f'<section class="home-features"><ol class="card-grid">{cards}</ol></section>')
    boxes, bx = h.get("boxes") or {}, []
    w = boxes.get("world")
    if w and w.get("items"):
        lis = "".join(f'<li><a {href_attr(resolve_link(i["url"]))}>{esc(i["title"])}</a></li>' for i in w["items"])
        bx.append(f'<div class="box box--world"><h2>{esc(w.get("title", ""))}</h2><ul>{lis}</ul></div>')
    ph = boxes.get("philately")
    if ph and ph.get("url"):
        im = img(ph["image"], "", sizes="(max-width: 700px) 100vw, 360px") if ph.get("image") else ""
        bx.append(f'<div class="box box--philately"><a {href_attr(ph["url"])}>{im}<b>{esc(ph.get("title", ""))}</b></a></div>')
    ap = boxes.get("app")
    if ap and ap.get("link"):
        bx.append(f'<div class="box box--app"><h2>{esc(ap.get("title", ""))}</h2>{f"<p>{esc(ap["text"])}</p>" if ap.get("text") else ""}'
                  f'<a class="btn" {href_attr(resolve_link(ap["link"]["url"]))}>{esc(ap["link"]["title"])}</a></div>')
    if bx:
        parts.append(f'<section class="home-boxes">{"".join(bx)}</section>')
    return layout(lang=lang, url=home_url(lang), title=names["site"], body="\n".join(p for p in parts if p), main_class="home", pinned=True,
                  description=page.get("description") or t["homeDescription"], image=None, status=page.get("status"), alt=section_alt("home"))


# ---------------------------------------------------------------- search, GDPR, editor, 404


def search_index(lang):
    rows = []
    for it in [*by_lang(NEWS, lang), *by_lang(PRESS, lang), *by_lang(GALLERIES, lang)]:
        lead = it.get("excerpt") or ""
        rows.append({"u": it["url"], "t": it["title"], "d": it["date"][:10], "k": {"news": "news", "press": "press", "gallery": "gallery"}[it["type"]],
                     "x": plain(f"{lead} {plain(it['body'], 600)}", 600)})
    rows.sort(key=lambda r: r["d"], reverse=True)
    for p in by_lang(list(PAGES.values()), lang):
        if p.get("redirect") or p["src"] == "(synthetic)" and not p["body"]:
            continue
        rows.append({"u": p["url"], "t": p["title"], "d": (p.get("modified") or "")[:10], "k": "page",
                     "x": plain(f"{p.get('description') or ''} {plain(p['body'], 600)}", 600)})
    return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))


def render_search(lang):
    t = I18N[lang]
    url = sec("search", lang)
    skeleton = "".join("<span></span>" for _ in range(6))
    body = f"""
<div class="wrap page page--simple">
 <header class="page-head"><h1 class="display">{esc(t['search'])}</h1></header>
 <form class="search-form" role="search" action="" method="get"><label class="visually-hidden" for="search-q">{esc(t['searchLabel'])}</label><input type="search" name="q" id="search-q" autocomplete="off" placeholder="{esc(t['searchPlaceholder'])}"><button type="submit">{esc(t['search'])}</button></form>
 <p class="search-status" role="status" aria-live="polite"></p>
 <div class="search-results" data-state="idle"><div class="skeleton search-skeleton" aria-hidden="true">{skeleton}</div><ol class="card-grid card-grid--text" id="search-list"></ol></div>
 <noscript><p>{esc(t['searchNoscript'])} <a href="{sec('news', lang)}">{esc(t['news'])}</a></p></noscript>
</div>"""
    return layout(lang=lang, url=url, title=t["search"], body=body, description=t["searchLabel"], main_class="search-page", noindex=True,
                  alt=section_alt("search"), scripts=["/js/search.js"])


def render_gdpr(lang):
    t = I18N[lang]
    url = sec("gdpr", lang)
    opts = "".join(f'<option value="{esc(label)}">{esc(t["gdprTypes"][k])}</option>' for k, label in
                   (("access", "Access to my data"), ("rectification", "Correction of my data"), ("erasure", "Erasure of my data"),
                    ("objection", "Objection to processing"), ("other", "Other")))
    body = f"""
<div class="wrap page page--simple">
 <header class="page-head"><h1 class="display">{esc(t['gdprTitle'])}</h1><p class="lead-s">{esc(t['gdprLead'])}</p></header>
 <form class="ne gdpr-form" data-form="data-request" action="/api/gdpr" method="post">
  <label class="ne-field"><span>{esc(t['gdprName'])} <i aria-hidden="true">*</i></span><input name="name" data-label="Name" required maxlength="100" autocomplete="name"></label>
  <label class="ne-field"><span>{esc(t['gdprEmail'])} <i aria-hidden="true">*</i></span><input type="email" name="email" data-label="Email" required maxlength="200" autocomplete="email"></label>
  <label class="ne-field"><span>{esc(t['gdprType'])}</span><select name="type" data-label="Type of request">{opts}</select></label>
  <label class="ne-field"><span>{esc(t['gdprMessage'])} <i aria-hidden="true">*</i></span><textarea name="message" data-label="Message" rows="6" required maxlength="5000"></textarea></label>
  <div class="visually-hidden" aria-hidden="true"><label>Leave this field empty<input name="_hp" tabindex="-1" autocomplete="off"></label></div>
  <p class="ne-msg" role="alert" hidden></p>
  <p><button class="btn" type="submit">{esc(t['gdprSend'])}</button></p>
 </form>
</div>"""
    return layout(lang=lang, url=url, title=t["gdprTitle"], body=body, description=t["gdprLead"], main_class="gdpr-page", alt=section_alt("gdpr"),
                  scripts=["/js/gdpr.js"])


EDITOR_FALLBACK = """<header class="page-head"><h1 class="display">News editor</h1></header>
<p>The staff editor (templates/editor.html) is not installed in this build.</p>"""


def render_editor():
    f = ROOT / "templates" / "editor.html"
    frag = f.read_text(encoding="utf-8") if f.exists() else EDITOR_FALLBACK
    if "<h1" not in frag:
        frag = '<header class="page-head"><h1 class="display">News editor</h1></header>' + frag
    if 'id="news-app"' not in frag:
        frag = f'<div class="wrap page page--simple ne" id="news-app">{frag}</div>'
    tail = (f'<link rel="stylesheet" href="/js/vendor/quill-2.0.3/quill.snow.css">\n<script src="/js/vendor/quill-2.0.3/quill.js"></script>\n'
            f'<script src="/js/news-editor.js?v={ASSET_VERSION}"></script>')
    return layout(lang=DEFAULT_LANG, url=EDITOR_URL, title="News editor", body=frag, description="Staff page for publishing news, press releases and galleries.",
                  noindex=True, alt={}, hreflang=False, tail=tail)


def editor_posts():
    rows = []
    for it in [*ALL_NEWS, *ALL_PRESS, *ALL_GALLERIES]:
        rows.append({"path": it["src"], "type": it["type"], "lang": it["lang"], "url": it["url"], "title": it["title"], "date": it["date"][:16],
                     "author": it.get("author"), "editedBy": it.get("editedBy"), "draft": bool(it.get("draft")), "pinned": bool(it.get("pinned")),
                     "translations": it.get("translations") or {}})
    return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))


def render_404():
    langs = []
    bases = [b for l in LANGS for b in (sec("news", l), sec("press", l), sec("galleries", l))]
    for l in LANGS:
        t = I18N[l]
        head = (f'<h1 class="display">{esc(t["notFound"])}</h1>' if l == DEFAULT_LANG
                else f'<p class="display nf-title" role="heading" aria-level="1">{esc(t["notFound"])}</p>')
        langs.append(f'<section class="nf" lang="{l}"{"" if l == DEFAULT_LANG else " hidden"}><header class="page-head">{head}</header>'
                     f'<div class="prose"><p>{esc(t["notFoundText"])}</p><p data-archive-note hidden>{esc(t["archiveNote"])}</p>'
                     f'<p><a class="link-strong" href="{home_url(l)}">{esc(t["home"])}</a> · <a class="link-strong" href="{sec("news", l)}">{esc(t["news"])}</a>'
                     f' · <a class="link-strong" href="{sec("search", l)}">{esc(t["search"])}</a></p></div></section>')
    body = f'<div class="wrap page page--simple" id="not-found">{"".join(langs)}</div>'
    return layout(lang=DEFAULT_LANG, url="/404.html", title=I18N[DEFAULT_LANG]["notFound"], body=body, description=I18N[DEFAULT_LANG]["notFoundText"],
                  noindex=True, alt={}, hreflang=False, archive_bases=bases)


# ---------------------------------------------------------------- feeds, sitemap, redirects, headers


def rss(lang):
    names, t = SITE["names"][lang], I18N[lang]
    try:
        tz = ZoneInfo(SITE.get("timezone", "Europe/Rome"))
    except Exception:
        tz = None

    def pub(n):
        d = datetime.fromisoformat(n["date"])
        if tz:
            d = d.replace(tzinfo=tz)
            return d.strftime("%a, %d %b %Y %H:%M:00 %z")
        return d.strftime("%a, %d %b %Y %H:%M:00 +0000")
    items = "".join(
        f"<item><title>{esc(n['title'])}</title><link>{SITE['baseUrl']}{esc(n['url'])}</link><guid>{SITE['baseUrl']}{esc(n['url'])}</guid>"
        f"<pubDate>{pub(n)}</pubDate><description>{esc(n.get('excerpt') or plain(n['body'], 300))}</description></item>"
        for n in by_lang(NEWS, lang)[:30])
    return (f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{esc(names["site"])} – {esc(t["news"])}</title>'
            f'<link>{SITE["baseUrl"]}{home_url(lang)}</link><description>{esc(names["order"])}</description><language>{lang}</language>{items}</channel></rss>')


def sitemap_xml():
    out = ['<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for url, alt in SITEMAP:
        links = "".join(f'<xhtml:link rel="alternate" hreflang="{l}" href="{SITE["baseUrl"]}{esc(u)}"/>' for l, u in alt_links(alt).items())
        out.append(f"<url><loc>{SITE['baseUrl']}{esc(url)}</loc>{links}</url>")
    return "".join(out) + "</urlset>"


VERCEL = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))  # headers and redirects live here; other hosts get _headers and _redirects
HEADERS = "".join(h["source"].replace("(.*)", "*") + "\n" + "".join(f"  {x['key']}: {x['value']}\n" for x in h["headers"]) for h in VERCEL.get("headers", []))


def vercel_redirects():
    rules = []
    for r in VERCEL.get("redirects", []):
        if r.get("has") or r.get("missing"):
            continue  # conditions (query strings) cannot be written as a static _redirects line; vercel.json applies them
        src = r["source"].replace(":path*", "*").replace("(.*)", "*")
        if re.search(r"[(){}?]|:\w", src):
            continue
        rules.append((src, r["destination"].replace(":path*", ":splat").replace("$1", ":splat")))
    return rules


def redirect_entries():
    """(from, to, title) for content/redirects.json and for pages that are only a redirect."""
    out, seen = [], set()
    for r in REDIRECT_FILE:
        if isinstance(r, dict) and safe_url(r.get("from", "")) and r.get("to"):
            out.append((r["from"], r["to"], r.get("title")))
            seen.add(r["from"])
    for p in ALL_PAGES:
        if p.get("redirect") and p["url"] not in seen:
            out.append((p["url"], p["redirect"], None))
    return out


# ---------------------------------------------------------------- build


def build():
    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(STATIC, DIST)
    redirects = redirect_entries()
    redirect_sources = {a for a, _, _ in redirects}
    page_redirects = {p["url"] for p in ALL_PAGES if p.get("redirect")}
    for lang in LANGS:
        write(home_url(lang), render_home(lang), sitemap=True, alt=section_alt("home"))
        render_news(lang)
        render_galleries(lang)
        write(sec("search", lang), render_search(lang))
        write(sec("gdpr", lang), render_gdpr(lang), sitemap=True, alt=section_alt("gdpr"))
        (DIST / "search").mkdir(exist_ok=True)
        (DIST / "search" / f"index.{lang}.json").write_text(search_index(lang), encoding="utf-8")
        feed = DIST / sec("feed", lang).lstrip("/")
        feed.parent.mkdir(parents=True, exist_ok=True)
        feed.write_text(rss(lang), encoding="utf-8")
    listing_urls = {sec(k, l) for k in ("news", "galleries") for l in LANGS}  # intro text only, the build writes these
    own_urls = listing_urls | {sec(k, l) for k in ("search", "gdpr") for l in LANGS} | HOME_URLS
    for url, p in PAGES.items():
        if url in HOME_URLS or p.get("template") == "home" or url in listing_urls:
            continue
        if url in own_urls:
            warn(f"page at a URL the build owns ignored: {url}")
            continue
        if p.get("redirect"):
            write(url, render_redirect_stub(url, p["redirect"], p["title"], p["lang"]))
            continue
        tpl = p.get("template") or "default"
        pages_n = 1
        if tpl == "press-releases":
            pages_n = n_pages_of(by_lang(PRESS, p["lang"]))
        elif tpl == "publications":
            pages_n = n_pages_of(collection_filter(p["lang"], "publications")[1])
        elif tpl == "in-the-news":
            pages_n = n_pages_of(collection_filter(p["lang"], "in-the-news")[1])
        for i in range(1, pages_n + 1):
            write(page_url(url, i), render_page(p, i), sitemap=i == 1)
    for lang in LANGS:  # publication categories
        c = COLL[lang].get("publications")
        for cat in (c or {}).get("categories") or []:
            if not safe_url(cat.get("url", "")) or cat["url"] in WRITTEN:
                continue
            _, items = collection_filter(lang, "publications", cat["key"])
            n = n_pages_of(items)
            for i in range(1, n + 1):
                cards = pub_tabs(lang, c, cat["key"]) + grid([publication_card(x, lang) for x in chunk(items, i)], lang)
                body = f"""
<div class="wrap">{crumbs_html([(c["title"], c["url"]), (cat["title"], cat["url"])], lang)}</div>
<div class="wrap page page--listing"><header class="page-head"><h1 class="display">{esc(cat["title"])}</h1></header>{cards}{pager_html(cat["url"], i, n, lang)}</div>"""
                write(page_url(cat["url"], i), layout(lang=lang, url=page_url(cat["url"], i), title=page_suffix(cat["title"], i, lang), body=body,
                                                      description=f"{cat['title']} – {c['title']}", alt={}, hreflang=False), sitemap=i == 1, alt={})
    for items, key in ((NEWS, "news"), (PRESS, "press"), (GALLERIES, "gallery")):
        for lang in LANGS:
            lst = by_lang(items, lang)
            for it in lst:
                note_media(it["body"], it["url"])
                write(it["url"], render_single(it, lst, {"news": "news", "press": "pressList", "gallery": "galleries"}[key]), sitemap=True)
    for src, dst, title in redirects:
        if not src.endswith("/"):
            continue
        if src in WRITTEN:
            if src not in page_redirects:
                warn(f"redirect source is also a built page, skipped: {src}")
                redirect_sources.discard(src)
            continue
        lang = lang_of_path(src)
        write(src, render_redirect_stub(src, dst, title or I18N[lang]["redirecting"] + " " + dst, lang))
    write(EDITOR_URL, render_editor())
    (DIST / EDITOR_URL.strip("/")).mkdir(parents=True, exist_ok=True)
    (DIST / EDITOR_URL.strip("/") / "posts.json").write_text(editor_posts(), encoding="utf-8")
    (DIST / "404.html").write_text(render_404(), encoding="utf-8")
    (DIST / "sitemap.xml").write_text(sitemap_xml(), encoding="utf-8")
    (DIST / "robots.txt").write_text(
        (f"User-agent: *\nAllow: /\nDisallow: {EDITOR_URL}\nDisallow: /api/\n\nSitemap: {SITE['baseUrl']}/sitemap.xml\n") if PRODUCTION
        else "User-agent: *\nDisallow: /\n", encoding="utf-8")
    (DIST / "feed.xml").write_text(rss(DEFAULT_LANG), encoding="utf-8")
    (DIST / "_headers").write_text(HEADERS + ("" if PRODUCTION else "/*\n  X-Robots-Tag: noindex, nofollow\n"), encoding="utf-8")
    lines, seen = [], set()
    for a, b in [(a, b) for a, b, _ in redirects if a in redirect_sources or not a.endswith("/")] + vercel_redirects():
        if a not in seen:
            seen.add(a)
            lines.append(f"{a} {b} 301\n")
    (DIST / "_redirects").write_text("".join(lines), encoding="utf-8")
    report()


def report():
    total = len(ALL_NEWS) + len(ALL_PRESS) + len(ALL_GALLERIES)
    if UNKNOWN_EMBEDS:
        warn(f"embeds from unsupported hosts turned into links: {len(UNKNOWN_EMBEDS)} ({', '.join(sorted(set(UNKNOWN_EMBEDS))[:5])})")
    if MISSING_MEDIA:
        warn(f"{len(MISSING_MEDIA)} referenced /media files do not exist, e.g. {', '.join(sorted(MISSING_MEDIA)[:5])}")
    for w in WARNINGS[:40]:
        print(f"  warning: {w}")
    if len(WARNINGS) > 40:
        print(f"  … and {len(WARNINGS) - 40} more warnings")
    print(f"built {len(PAGES)} pages, {len(NEWS)} news, {len(PRESS)} press releases, {len(GALLERIES)} galleries "
          f"({total - len(NEWS) - len(PRESS) - len(GALLERIES)} drafts or scheduled), {len(WRITTEN)} urls, "
          f"{'production' if PRODUCTION else 'preview'} → {DIST}")
    if ERRORS:
        for e in ERRORS:
            print(f"  ERROR: {e}")
        sys.exit(1)


# ---------------------------------------------------------------- local preview server


def serve(port=8000):
    import http.server
    import functools
    rules = [l.split() for l in (DIST / "_redirects").read_text().splitlines() if l.strip()]
    homes = {home_url(l): l for l in LANGS}
    headers, types = {}, {}  # site-wide headers; exact-path Content-Type overrides
    block = None
    for line in (DIST / "_headers").read_text().splitlines():
        if line and not line.startswith(" "):
            block = line.strip()
        elif line.strip():
            k, v = line.strip().split(":", 1)
            if block == "/*":
                headers[k] = v.strip()
            elif k == "Content-Type":
                types[block] = v.strip()

    class H(http.server.SimpleHTTPRequestHandler):
        def guess_type(self, path):
            return types.get(self.path.split("?")[0]) or super().guess_type(path)

        def end_headers(self):
            for k, v in headers.items():
                if k == "Strict-Transport-Security":
                    continue  # local server is plain HTTP
                if k == "Content-Security-Policy":
                    v = v.replace("; upgrade-insecure-requests", "")
                self.send_header(k, v)
            super().end_headers()

        def _redirect(self, dst):
            self.send_response(301)
            self.send_header("Location", dst)
            self.end_headers()

        def do_GET(self):
            parts = urlsplit(self.path)
            path, query = parts.path, parse_qs(parts.query)
            if "s" in query and path in homes:  # WordPress search links
                return self._redirect(f"{sec('search', homes[path])}?q={quote(query['s'][0])}")
            m = re.match(r"^/(?:(it|fr|de|es)/)?(\d{4})/(?:page/\d+/)?$", path)
            if m and query.get("post_type") == ["news"]:
                return self._redirect(f"{sec('news', m.group(1) or DEFAULT_LANG)}{m.group(2)}/")
            for src, dst, _ in rules:
                if src.endswith("*") and path.startswith(src[:-1]):
                    return self._redirect(dst.replace(":splat", path[len(src) - 1:]))
                if src == path:
                    return self._redirect(dst)
            fs_path = unquote(path).lstrip("/")  # media file names may carry diacritics; the URL is percent-encoded
            if not (DIST / fs_path).exists() and not (DIST / fs_path / "index.html").exists():
                self.send_response(404)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write((DIST / "404.html").read_bytes())
                return
            self.path = path
            super().do_GET()

        do_HEAD = do_GET

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(H, directory=str(DIST)))
    print(f"serving http://127.0.0.1:{port}/")
    httpd.serve_forever()


if __name__ == "__main__":
    build()
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        serve(int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 8000)
