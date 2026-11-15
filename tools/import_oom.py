#!/usr/bin/env python3
"""Importer for orderofmalta.int (WordPress + WPML) into the static content tree.

Standard library + Pillow only.  See docs/build-spec.md sections 0, 2 and 3.

    python3 tools/import_oom.py [--since 2025-01-01] [--langs en,it,fr,de,es]
            [--types menus,pages,categories,news,press,galleries,collections]
            [--limit N] [--no-media] [--refresh] [--workers 4]

Re-runnable: every HTTP response is cached in .cache/oom/; a content file whose
front matter says "imported": false is never overwritten; files are rewritten
only when their content changed; nothing is ever deleted.
"""
import argparse
import hashlib
import html
import io
import json
import os
import re
import shutil
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
MEDIA_DIR = ROOT / "static" / "media"
CACHE = ROOT / ".cache" / "oom"
SITE = "https://www.orderofmalta.int"
HOSTS = ("www.orderofmalta.int", "orderofmalta.int", "smom", "www.smom")
UA = "Mozilla/5.0 (compatible; ContentMigrator/1.0)"
LANGS = ["en", "it", "fr", "de", "es"]
PREFIX = {"en": "", "it": "/it", "fr": "/fr", "de": "/de", "es": "/es"}
LANG_LABEL = {"en": "english", "it": "italiano", "fr": "francais", "de": "deutsch", "es": "espanol"}
TYPES_ALL = ["menus", "pages", "categories", "news", "press", "galleries", "collections"]
SECTIONS = {
    "news": {"en": "/news/", "it": "/it/notizie/", "fr": "/fr/actualites/", "de": "/de/nachrichten/", "es": "/es/noticias/"},
    "press": {"en": "/press-releases/", "it": "/it/comunicati-stampa/", "fr": "/fr/communiques-de-presse/", "de": "/de/pressemitteilungen/", "es": "/es/comunicados-de-prensa/"},
    "pressList": {"en": "/press-publications/press-releases/", "it": "/it/media-e-pubblicazioni/comunicati-stampa/", "fr": "/fr/press-et-publications/communiques-de-presse/", "de": "/de/presse-und-veroeffentlichungen/pressemitteilungen/", "es": "/es/prensa-y-publicaciones/comunicados-de-prensa/"},
    "galleries": {"en": "/photo-and-video-galleries/", "it": "/it/gallerie-foto-e-video/", "fr": "/fr/galeries-photo-et-video/", "de": "/de/foto-und-videogalerien/", "es": "/es/galerias-de-fotos-y-videos/"},
    "newsCategories": {"en": "/news-categories/", "it": "/it/categorie-notizia/", "fr": "/fr/categories-de-actualites/", "de": "/de/nachrichten-kategorien/", "es": "/es/categorias-de-noticias/"},
    "galleryTypes": {"en": "/gallery-type/", "it": "/it/tipi-di-galleria/", "fr": "/fr/types-de-galeries/", "de": "/de/galerie-typen/", "es": "/es/tipos-de-galerias/"},
}
# gallery type slugs per language: photo, album, video
GALLERY_TYPE_SLUGS = {
    "en": ("single-picture", "gallery", "video"), "it": ("singola-foto", "gallery-it", "video-it"),
    "fr": ("image-unique", "gallery-fr", "video-fr"), "de": ("einzelnes-bild", "gallery-de", "video-de"),
    "es": ("imagen-unica", "gallery-es", "video-es"),
}
# the site's WordPress clock runs on a fixed UTC+2 offset (checked against REST date/date_gmt)
SITE_UTC_OFFSET_H = 2

REPORT = {
    "counts": {}, "no_translation": [], "dropped_terms": [], "skipped_files": [], "unknown_embeds": [],
    "unmapped": [], "skipped_pages": [], "notes": [], "failed": [], "external_links": [],
}
_report_lock = threading.Lock()


def note(key, value):
    with _report_lock:
        REPORT[key].append(value)


# ---------------------------------------------------------------- HTTP with cache


class Http:
    def __init__(self, workers=4, refresh=False):
        self.refresh = refresh
        self.sem = threading.Semaphore(max(1, min(4, workers)))
        self.pool = ThreadPoolExecutor(max_workers=max(1, min(4, workers)))
        self.network_requests = 0
        self.lock = threading.Lock()
        CACHE.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _key(url):
        return hashlib.sha1(url.encode("utf-8")).hexdigest()

    def _paths(self, url):
        k = self._key(url)
        d = CACHE / k[:2]
        return d / (k + ".json"), d / (k + ".body")

    def get(self, url, accept=None):
        """Return dict(status, final, body(bytes), ctype). Cached (also 404s)."""
        url = url.replace(" ", "%20")
        mp, bp = self._paths(url)
        if not self.refresh and mp.exists() and bp.exists():
            try:
                meta = json.loads(mp.read_text(encoding="utf-8"))
                return {"status": meta["status"], "final": meta["final"], "ctype": meta.get("ctype", ""), "body": bp.read_bytes(), "headers": meta.get("headers", {})}
            except Exception:
                pass
        res = self._fetch(url, accept)
        if res["status"] in (200, 301, 302, 400, 401, 403, 404, 410):
            mp.parent.mkdir(parents=True, exist_ok=True)
            tmp = bp.with_suffix(".tmp")
            tmp.write_bytes(res["body"])
            tmp.replace(bp)
            mp.write_text(json.dumps({"status": res["status"], "final": res["final"], "ctype": res["ctype"], "headers": res.get("headers", {})}), encoding="utf-8")
        return res

    def _fetch(self, url, accept=None):
        quoted = urllib.parse.quote(url, safe=":/%?=&+#@;,~!$'()*[]")
        last = None
        for attempt in range(5):
            with self.sem:
                time.sleep(0.12)
                try:
                    with self.lock:
                        self.network_requests += 1
                    req = urllib.request.Request(quoted, headers={"User-Agent": UA, "Accept": accept or "*/*", "Accept-Language": "en"})
                    with urllib.request.urlopen(req, timeout=60) as r:
                        body = r.read()
                        hdrs = {k.lower(): v for k, v in r.headers.items() if k.lower() in ("x-wp-total", "x-wp-totalpages", "content-type")}
                        return {"status": r.status, "final": r.geturl(), "ctype": r.headers.get("content-type", ""), "body": body, "headers": hdrs}
                except urllib.error.HTTPError as e:
                    if e.code in (400, 401, 403, 404, 410):
                        return {"status": e.code, "final": url, "ctype": "", "body": b"", "headers": {}}
                    last = f"HTTP {e.code}"
                except Exception as e:  # network trouble: back off and retry
                    last = repr(e)
            time.sleep(2 ** attempt * 1.5)
        note("failed", f"{url}: {last}")
        return {"status": 599, "final": url, "ctype": "", "body": b"", "headers": {}}

    def text(self, url):
        r = self.get(url)
        return r["body"].decode("utf-8", "replace"), r

    def json(self, url):
        r = self.get(url, accept="application/json")
        if r["status"] != 200:
            return None, r
        try:
            return json.loads(r["body"].decode("utf-8")), r
        except ValueError:
            return None, r

    def map(self, fn, items):
        return list(self.pool.map(fn, items))


# ---------------------------------------------------------------- tolerant DOM

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
RAW = {"script", "style"}
INLINE = {"a", "span", "strong", "b", "em", "i", "u", "s", "small", "sup", "sub", "font", "label", "abbr", "mark", "code", "button"}
BLOCK = {"div", "p", "ul", "ol", "li", "table", "tr", "td", "th", "section", "article", "blockquote", "figure", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "form", "iframe", "aside", "header", "footer", "nav"}
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


class Node:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag, attrs=None, parent=None):
        self.tag, self.attrs, self.children, self.parent = tag, dict(attrs or {}), [], parent

    def get(self, k, d=""):
        v = self.attrs.get(k)
        return d if v is None else v

    @property
    def classes(self):
        return self.attrs.get("class", "").split() if self.attrs.get("class") else []

    def has(self, cls):
        return cls in self.classes

    def has_prefix(self, prefix):
        return any(c.startswith(prefix) for c in self.classes)

    def elements(self):
        return [c for c in self.children if isinstance(c, Node)]

    def walk(self):
        for c in self.children:
            if isinstance(c, Node):
                yield c
                yield from c.walk()

    def find_all(self, tag=None, cls=None, pred=None):
        out = []
        for n in self.walk():
            if tag and n.tag != tag:
                continue
            if cls and not n.has(cls):
                continue
            if pred and not pred(n):
                continue
            out.append(n)
        return out

    def find(self, tag=None, cls=None, pred=None):
        for n in self.walk():
            if tag and n.tag != tag:
                continue
            if cls and not n.has(cls):
                continue
            if pred and not pred(n):
                continue
            return n
        return None

    def text(self):
        parts = []

        def rec(n):
            for c in n.children:
                if isinstance(c, str):
                    parts.append(c)
                elif c.tag == "br":
                    parts.append(" ")
                else:
                    rec(c)
        rec(self)
        return re.sub(r"\s+", " ", "".join(parts).replace("\xa0", " ")).strip()


class _Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root")
        self.stack = [self.root]
        self.raw = None

    def _top(self):
        return self.stack[-1]

    def handle_starttag(self, tag, attrs):
        if tag in RAW:
            self.raw = tag
            return
        # implied end tags
        if tag in BLOCK:
            i = len(self.stack) - 1
            while i > 0:
                t = self.stack[i].tag
                if t in INLINE:
                    i -= 1
                    continue
                if t in HEADINGS or t == "p":
                    del self.stack[i:]
                break
        if tag == "li":
            for i in range(len(self.stack) - 1, 0, -1):
                t = self.stack[i].tag
                if t == "li":
                    del self.stack[i:]
                    break
                if t in ("ul", "ol"):
                    break
        if tag in ("td", "th"):
            for i in range(len(self.stack) - 1, 0, -1):
                t = self.stack[i].tag
                if t in ("td", "th"):
                    del self.stack[i:]
                    break
                if t in ("tr", "table"):
                    break
        if tag == "tr":
            for i in range(len(self.stack) - 1, 0, -1):
                t = self.stack[i].tag
                if t == "tr":
                    del self.stack[i:]
                    break
                if t == "table":
                    break
        n = Node(tag, [(k, v) for k, v in attrs], self._top())
        self._top().children.append(n)
        if tag not in VOID:
            self.stack.append(n)

    def handle_startendtag(self, tag, attrs):
        if tag in RAW:
            return
        n = Node(tag, [(k, v) for k, v in attrs], self._top())
        self._top().children.append(n)
        if tag not in VOID and tag not in ("a", "span", "div", "p", "i"):
            pass

    def handle_endtag(self, tag):
        if tag in RAW:
            self.raw = None
            return
        if tag in VOID:
            return
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if self.raw:
            return
        self._top().children.append(data)


def parse(markup):
    b = _Builder()
    b.feed(markup)
    b.close()
    return b.root


def attr_text(s):
    return re.sub(r"\s+", " ", html.unescape(s or "").replace("\xa0", " ")).strip()


def norm_text(s):
    return re.sub(r"\s+", " ", html.unescape(s or "").replace("\xa0", " ")).strip()


# ---------------------------------------------------------------- pure helpers


def file_slug(slug):
    s = urllib.parse.unquote(slug).lower()
    s = re.sub(r"[^a-z0-9-]", "-", s)
    return s[:120] or "item"


def decode_cfemail(hexs):
    b = bytes.fromhex(hexs)
    key = b[0]
    return bytes(c ^ key for c in b[1:]).decode("utf-8", "replace")


SIZE_SUFFIX = re.compile(r"-(?:scaled|rotated|e\d{10,}|\d{2,5}x\d{2,5})(?=(?:-(?:scaled|rotated|e\d{10,}|\d{2,5}x\d{2,5}))*\.\w+$)")


def strip_size_suffix(url):
    """/2026/11/name-1600x852.jpg -> /2026/11/name.jpg ; -scaled and -e<digits> too."""
    path, dot, ext = url.rpartition(".")
    if not dot:
        return url
    for _ in range(3):
        new = re.sub(r"-(?:scaled|rotated|e\d{10,}|\d{2,5}x\d{2,5})$", "", path)
        if new == path:
            break
        path = new
    return path + "." + ext


def media_name(rel):
    """upload relative path -> static/media relative path with lower-case [a-z0-9._-] name."""
    rel = urllib.parse.unquote(rel)
    folder, _, name = rel.rpartition("/")
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    stem = re.sub(r"[^a-z0-9._-]", "-", stem.lower())
    stem = stem.replace("smom", "om")  # the four-letter acronym is never written by us, not even in file names
    stem = re.sub(r"-{2,}", "-", stem).strip("-.") or "file"
    ext = re.sub(r"[^a-z0-9]", "", ext.lower())
    return (folder + "/" if folder else "") + stem + (("." + ext) if ext else "")


def date_iso(dt):
    return dt[:16]


def dmy_to_iso(s):
    """'02/11/2026' or '7 Novembre 2026' / '7. November 2026' / '7 de noviembre de 2026' -> '2026-11-07'."""
    s = s or ""
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    m = re.search(r"(\d{1,2})\.?\s*(?:de\s+|d')?([^\W\d_]+)\.?,?\s*(?:de\s+)?(\d{4})", s)
    if m:
        name = strip_accents(m.group(2).lower())
        for lg in MONTHS:
            if name in MONTHS[lg]:
                return f"{m.group(3)}-{MONTHS[lg].index(name) + 1:02d}-{int(m.group(1)):02d}"
    return None


def utc_to_local(iso):
    """'2026-11-09T14:31:02+00:00' -> '2026-11-09T16:31' (site clock is UTC+2)."""
    import datetime as dt
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})", iso or "")
    if not m:
        return None
    d = dt.datetime(*map(int, m.groups())) + dt.timedelta(hours=SITE_UTC_OFFSET_H)
    return d.strftime("%Y-%m-%dT%H:%M")


def abs_url(href, base=SITE + "/"):
    return urllib.parse.urljoin(base, (href or "").strip())


def local_path(href):
    """Root-relative path (with query dropped, fragment kept) for same-site URLs, else None."""
    href = (href or "").strip()
    if href.startswith("//"):
        href = "https:" + href
    if href.startswith("/") and not href.startswith("//"):
        u = urllib.parse.urlparse(href)
        return u.path + (("#" + u.fragment) if u.fragment else "")
    u = urllib.parse.urlparse(href)
    if u.scheme in ("http", "https") and u.netloc.lower() in HOSTS:
        return (u.path or "/") + (("#" + u.fragment) if u.fragment else "")
    return None


def with_slash(path):
    base, _, frag = path.partition("#")
    if base and not base.endswith("/") and "." not in base.rsplit("/", 1)[-1]:
        base += "/"
    return base + (("#" + frag) if frag else "")


def write_text_if_changed(path, text):
    path = Path(path)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def split_front(text):
    parts = text.split("---\n", 2)
    if len(parts) < 3 or parts[0] != "":
        return None, text
    return json.loads(parts[1]), parts[2]


def dump_front(meta, body):
    return "---\n" + json.dumps(meta, ensure_ascii=False, indent=1) + "\n---\n" + body.strip("\n") + "\n"


def write_content(path, meta, body, stats):
    """Write a front-matter file unless a human owns it. Returns 'new'|'changed'|'same'|'protected'."""
    path = Path(path)
    meta = {**meta, "imported": True}
    new = dump_front(meta, body)
    if path.exists():
        old = path.read_text(encoding="utf-8")
        try:
            om, _ = split_front(old)
        except ValueError:
            om = None
        if om is not None and om.get("imported") is False:
            stats["protected"] = stats.get("protected", 0) + 1
            return "protected"
        if old == new:
            stats["same"] = stats.get("same", 0) + 1
            return "same"
        path.write_text(new, encoding="utf-8")
        stats["changed"] = stats.get("changed", 0) + 1
        return "changed"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new, encoding="utf-8")
    stats["new"] = stats.get("new", 0) + 1
    return "new"


# ---------------------------------------------------------------- media

DOC_EXT = {"pdf", "doc", "docx", "xls", "xlsx", "zip", "ppt", "pptx", "odt", "ods", "rtf", "txt", "csv", "epub"}
IMG_EXT = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "tif", "tiff"}
MAX_DOC_BYTES = 25 * 1024 * 1024
UPLOADS = "/wp-content/uploads/"


def upload_rel(url):
    """Relative upload path of a same-site upload URL, or None."""
    u = urllib.parse.urlparse(url if "://" in url else SITE + (url if url.startswith("/") else "/" + url))
    if u.netloc.lower() not in HOSTS and "://" in url:
        return None
    if UPLOADS not in u.path:
        return None
    return urllib.parse.unquote(u.path.split(UPLOADS, 1)[1])


class Media:
    """Downloads each upload once; dedupes through content/media-map.json."""

    def __init__(self, http, enabled=True):
        self.http = http
        self.enabled = enabled
        self.path = CONTENT / "media-map.json"
        self.map = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        self.used = {v["path"]: k for k, v in self.map.items() if "path" in v}
        self.lock = threading.Lock()
        self.locks = {}
        self.dirty = 0
        self.total_new = 0
        self.skipped = []

    def save(self):
        if not self.dirty:
            return
        with self.lock:
            text = json.dumps(self.map, ensure_ascii=False, indent=0, sort_keys=True) + "\n"
            write_text_if_changed(self.path, text)
            self.dirty = 0

    @staticmethod
    def key_for(url):
        rel = upload_rel(url)
        if rel is None:
            return None
        return strip_size_suffix(rel)

    def _dest(self, key, ext):
        """Pick a unique local path for this upload key."""
        base = media_name(key)
        stem = base.rsplit(".", 1)[0] if "." in base else base
        cand = stem + "." + ext
        n = 2
        with self.lock:
            while cand in self.used and self.used[cand] != key:
                cand = f"{stem}-{n}.{ext}"
                n += 1
            self.used[cand] = key
        return cand

    def _lock_for(self, key):
        with self.lock:
            return self.locks.setdefault(key, threading.Lock())

    def _download(self, url):
        """Raw download without caching; returns bytes or None."""
        quoted = urllib.parse.quote(url, safe=":/%?=&+#@;,~!$'()*[]")
        for attempt in range(4):
            with self.http.sem:
                time.sleep(0.05)
                try:
                    with self.http.lock:
                        self.http.network_requests += 1
                    req = urllib.request.Request(quoted, headers={"User-Agent": UA})
                    with urllib.request.urlopen(req, timeout=120) as r:
                        return r.read()
                except urllib.error.HTTPError as e:
                    if e.code in (400, 401, 403, 404, 410):
                        return None
                except Exception:
                    pass
            time.sleep(2 ** attempt * 1.5)
        return None

    def image(self, url, max_edge=1600):
        """Return {'path','w','h'} (local /media path) or None."""
        key = self.key_for(url)
        if key is None:
            return None
        ext = key.rsplit(".", 1)[-1].lower() if "." in key else ""
        if ext in DOC_EXT:
            return None
        with self.lock:
            hit = self.map.get(key)
        if hit and "path" in hit and (MEDIA_DIR / hit["path"].lstrip("/").replace("media/", "", 1)).exists():
            return {"path": hit["path"], "w": hit.get("w"), "h": hit.get("h")}
        if hit and hit.get("skipped"):
            return None
        if not self.enabled:
            return None
        with self._lock_for(key):
            with self.lock:
                hit = self.map.get(key)
            if hit and "path" in hit and (MEDIA_DIR / hit["path"].lstrip("/").replace("media/", "", 1)).exists():
                return {"path": hit["path"], "w": hit.get("w"), "h": hit.get("h")}
            return self._fetch_image(key, url, ext, max_edge)

    def _fetch_image(self, key, url, ext, max_edge):
        orig = SITE + UPLOADS + urllib.parse.quote(key)
        data = self._download(orig)
        if data is None and abs_url(url) != orig:
            data = self._download(abs_url(url))
        if data is None:
            self._fail(key, "download failed")
            return None
        if ext == "svg":
            return self._svg(key, data)
        try:
            from PIL import Image, ImageOps
        except ImportError:
            self._fail(key, "Pillow missing")
            return None
        try:
            im = Image.open(io.BytesIO(data))
            im.load()
            im = ImageOps.exif_transpose(im)
        except Exception as e:
            self._fail(key, f"unreadable image ({e})")
            return None
        dest_rel = self._dest(key, "webp")
        dest = MEDIA_DIR / dest_rel
        w, h = save_webp(im, dest, max_edge)
        with self.lock:
            self.map[key] = {"path": "/media/" + dest_rel, "w": w, "h": h}
            self.dirty += 1
            self.total_new += 1
            if self.dirty >= 150:
                pass
        if self.dirty >= 150:
            self.save()
        return {"path": "/media/" + dest_rel, "w": w, "h": h}

    def _svg(self, key, data):
        txt = data.decode("utf-8", "replace")
        if re.search(r"<script|\son\w+\s*=|xlink:href\s*=\s*[\"']https?:|href\s*=\s*[\"']https?:|<foreignObject", txt, re.I):
            self._fail(key, "unsafe svg")
            return None
        dest_rel = self._dest(key, "svg")
        dest = MEDIA_DIR / dest_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        with self.lock:
            self.map[key] = {"path": "/media/" + dest_rel, "w": None, "h": None}
            self.dirty += 1
        return {"path": "/media/" + dest_rel, "w": None, "h": None}

    def document(self, url):
        """Copy a document; return its local /media path or None (kept absolute by the caller)."""
        key = self.key_for(url)
        if key is None:
            return None
        with self.lock:
            hit = self.map.get(key)
        if hit and "path" in hit and (MEDIA_DIR / hit["path"].replace("/media/", "", 1)).exists():
            return hit["path"]
        if hit and hit.get("skipped"):
            return None
        if not self.enabled:
            return None
        with self._lock_for(key):
            with self.lock:
                hit = self.map.get(key)
            if hit and "path" in hit:
                return hit["path"]
            data = self._download(SITE + UPLOADS + urllib.parse.quote(key))
            if data is None:
                self._fail(key, "document download failed")
                return None
            if len(data) > MAX_DOC_BYTES:
                self._fail(key, f"document larger than 25 MB ({len(data) // 1048576} MB)")
                return None
            ext = key.rsplit(".", 1)[-1].lower() if "." in key else "bin"
            dest_rel = self._dest(key, ext)
            # keep the original extension: _dest builds stem + ext
            dest = MEDIA_DIR / dest_rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            with self.lock:
                self.map[key] = {"path": "/media/" + dest_rel}
                self.dirty += 1
            return "/media/" + dest_rel

    def _fail(self, key, why):
        with self.lock:
            self.map[key] = {"skipped": why}
            self.dirty += 1
        note("skipped_files", f"{key}: {why}")

    def poster(self, yt_id):
        """YouTube poster -> static/media/embeds/youtube-<id>.webp"""
        dest = MEDIA_DIR / "embeds" / f"youtube-{yt_id}.webp"
        if dest.exists() or not self.enabled:
            return dest.exists()
        mk = f"yt-poster:{yt_id}"
        with self.lock:
            if self.map.get(mk, {}).get("skipped"):
                return False
        data = self._download(f"https://i.ytimg.com/vi/{yt_id}/hqdefault.jpg")
        if not data:
            with self.lock:
                self.map[mk] = {"skipped": "no poster"}
                self.dirty += 1
            return False
        try:
            from PIL import Image
            im = Image.open(io.BytesIO(data))
            im.load()
            save_webp(im, dest, 480, small=False)
            return True
        except Exception:
            return False


def save_webp(im, dest, max_edge, small=True):
    from PIL import Image
    try:
        if im.info.get("icc_profile"):
            from PIL import ImageCms
            src = ImageCms.ImageCmsProfile(io.BytesIO(im.info["icc_profile"]))
            im = ImageCms.profileToProfile(im, src, ImageCms.createProfile("sRGB"), outputMode="RGBA" if "A" in im.mode else "RGB")
    except Exception:
        pass
    if im.mode in ("P", "LA", "PA") or (im.mode == "RGBA"):
        im = im.convert("RGBA")
        if im.getextrema()[3][0] == 255:
            im = im.convert("RGB")
    elif im.mode != "RGB":
        im = im.convert("RGB")
    w, h = im.size
    if max(w, h) > max_edge:
        s = max_edge / max(w, h)
        im = im.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)
        w, h = im.size
    dest.parent.mkdir(parents=True, exist_ok=True)
    clean = Image.new(im.mode, im.size)
    clean.paste(im)  # drops every metadata block
    clean.save(dest, "WEBP", quality=76, method=6)
    if small and w > 640:
        sw = 480
        sh = max(1, round(h * sw / w))
        clean.resize((sw, sh), Image.LANCZOS).save(dest.with_name(dest.stem + "-480.webp"), "WEBP", quality=76, method=6)
    return w, h


# ---------------------------------------------------------------- body normaliser (spec 3.5)

DROP_TAGS = {"script", "style", "noscript", "form", "button", "select", "textarea", "input", "svg", "nav", "head", "link", "meta", "object", "embed", "canvas", "label", "map", "template"}
INLINE_MAP = {"strong": "strong", "b": "strong", "em": "em", "i": "em", "u": "u", "s": "s", "strike": "s", "del": "s", "sup": "sup", "sub": "sub"}
READ_ALL = re.compile(r"^(read all|read more|leggi tutto|lire tout|alles lesen|leer todo|leer m[aá]s)\b", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
KNOWN_LAYOUT = re.compile(
    r"^(row|col(-\w+)*|container(-lg)?|page-content|box-content-container(-text)?|title-borders|gry|trs|content|bottom-space|extra-mg|"
    r"d-flex|align-items-center|offset-lg-\d+|fade|show|active|spaced-table|alignleft|alignright|aligncenter|alignnone|"
    r"size-\w+|attachment-\w+|wp-image-\d+|wp-caption\w*|accordion\w*|collapse\w*|fa|fa-\w+|bi|bi-\w+|callout|js_url|"
    r"embed-container|small-heading|intro|table|tab-pane|tab-content|nav-pills|nav-item|nav-link|shift-img|"
    r"[a-z]{1,4}\d{1,3}|s\d|BCX\d|SCX\w+|NormalTextRun|SpellingError\w*|Contextual\w*|Grammar\w*|TextRun|EOP|OutlineElement|Paragraph|"
    r"__cf_email__|wp-block-\w+|has-\w+|screen-reader-text|sr-only|visually-hidden)$")


def esc(s):
    return html.escape(s, quote=False)


def esc_attr(s):
    return html.escape(s, quote=True)


def yt_id(url):
    m = re.search(r"(?:youtube(?:-nocookie)?\.com/(?:embed/|watch\?(?:[^#]*&)?v=|v/|shorts/)|youtu\.be/)([\w-]{6,})", url or "")
    return m.group(1) if m else None


def vimeo_id(url):
    m = re.search(r"vimeo\.com/(?:video/)?(\d+)", url or "")
    return m.group(1) if m else None


def watch_url(url):
    y = yt_id(url)
    if y:
        return f"https://www.youtube.com/watch?v={y}"
    v = vimeo_id(url)
    if v:
        return f"https://vimeo.com/{v}"
    return None


class Body:
    """Turns theme markup (or an editor fragment) into the body vocabulary of spec 3.5."""

    def __init__(self, media, lang, where="", teaser_img=None):
        self.media = media
        self.lang = lang
        self.where = where
        self.out = []
        self.related = []
        self.tail = []
        self.videos = []
        self.hoist = []
        self.teaser_img = teaser_img if teaser_img is not None else {}
        self.first_img = None  # (path, w, h, alt) of the first figure emitted
        self.img_cap = 1600
        self.self_url = None
        self.resolver = None

    # ---- links
    def link(self, href):
        href = (href or "").strip()
        if href.startswith("(") and href.endswith(")"):
            href = href[1:-1].strip()
        mal = re.search(r"/\((https?):/+([^)\s]+)\)?/?$", href)  # editor typo: site URL glued in front of "(https://other/...)"
        if mal:
            href = f"{mal.group(1)}://{mal.group(2)}"
        if not href or href == "#" or href.lower().startswith(("javascript:", "data:", "vbscript:")):
            return None
        if href.startswith("mailto:") or href.startswith("tel:"):
            return href.replace(" ", "")
        if re.fullmatch(r"[\w.+-]+@[\w-]+(\.[\w-]+)+", href):
            return "mailto:" + href
        ya = re.match(r"^(?:https?://(?:www\.)?orderofmalta\.int)?(/(?:it|fr|de|es)/|/)(\d{4})/(?:page/\d+/)?\?(?:[^#]*&)?post_type=news", href)
        if ya:
            lg = {"/it/": "it", "/fr/": "fr", "/de/": "de", "/es/": "es"}.get(ya.group(1), "en")
            return SECTIONS["news"][lg] + ya.group(2) + "/"
        m = re.search(r"/cdn-cgi/l/email-protection#([0-9a-fA-F]+)", href)
        if m:
            try:
                return "mailto:" + decode_cfemail(m.group(1))
            except Exception:
                return None
        if href.startswith("#"):
            return href
        if not re.match(r"^[a-z][a-z0-9+.-]*:", href, re.I) and not href.startswith("/") and re.match(r"^(www\.)?[\w-]+(\.[\w-]+)+(/|$)", href):
            href = "https://" + href
        if href.startswith("//"):
            href = "https:" + href
        lp = local_path(href)
        if lp is not None or href.startswith(("../", "./")) or (not re.match(r"^[a-z][a-z0-9+.-]*:", href, re.I) and not href.startswith("/")):
            if lp is None:
                lp = local_path(abs_url(href))
            if lp is None:
                return None
            path, _, frag = lp.partition("#")
            if "/wp-content/uploads/" in path:
                ext = path.rsplit(".", 1)[-1].lower() if "." in path.rsplit("/", 1)[-1] else ""
                if ext in DOC_EXT:
                    loc = self.media.document(SITE + path)
                    if loc:
                        return urllib.parse.quote(loc, safe="/%")
                    note("external_links", f"{self.where}: kept live file {path}")
                    return SITE + path
                if ext in IMG_EXT or ext == "svg":
                    r = self.media.image(SITE + path, self.img_cap)
                    return r["path"] if r else None
                return SITE + path
            if path.startswith("/wp-content/") or path.startswith("/wp-"):
                return None
            if path.startswith("/cdn-cgi/"):
                return None
            path = with_slash(path)
            if self.resolver and path != "/" and not path.endswith(".xml"):
                r = self.resolver(path)
                if not r.startswith("/"):
                    return r
                path = r
            return path + (("#" + frag) if frag else "")
        return href

    # ---- inline
    def inline(self, nodes, in_a=False):
        out = []
        for n in nodes:
            if isinstance(n, str):
                out.append(esc(n.replace("\xa0", " ") if False else n))
                continue
            t = n.tag
            if t in DROP_TAGS:
                continue
            if t == "br":
                out.append("<br>")
            elif t == "img":
                self.hoist_img(n)
            elif t == "iframe":
                self.hoist.append(self.iframe(n))
            elif t == "a":
                if n.get("data-fancybox") and n.find("img"):
                    for im in n.find_all("img"):
                        self.hoist_img(im, link_href=n.get("href"))
                    continue
                href = self.link(n.get("href"))
                inner = self.inline(n.children, in_a=True)
                if re.fullmatch(r"\s*(<br>)?\s*", inner):
                    continue
                if href and not in_a:
                    cls = ' class="btn"' if ("button" in n.classes or "btn" in n.classes) else ""
                    out.append(f'<a{cls} href="{esc_attr(href)}">{inner.strip()}</a>')
                else:
                    out.append(inner)
            elif t == "span" and n.has("__cf_email__"):
                try:
                    addr = decode_cfemail(n.get("data-cfemail"))
                    out.append(esc(addr) if in_a else f'<a href="mailto:{esc_attr(addr)}">{esc(addr)}</a>')
                except Exception:
                    pass
            elif t == "i" and (n.has("fa") or n.has_prefix("fa-") or n.has_prefix("bi")):
                continue
            elif t in INLINE_MAP:
                tag = INLINE_MAP[t]
                inner = self.inline(n.children, in_a)
                if inner.strip():
                    out.append(f"<{tag}>{inner}</{tag}>")
                else:
                    out.append(inner)
            elif t in ("span", "font", "small", "abbr", "mark", "code", "cite", "q", "label", "time", "address", "center"):
                out.append(self.inline(n.children, in_a))
            else:  # unknown inline-ish element: keep its text and links
                out.append(self.inline(n.children, in_a))
        s = "".join(out)
        s = re.sub(r"[ \t\r\n\xa0]+", " ", s)
        # the email text of a Cloudflare link is "[email protected]" when the script had not run
        return s

    def hoist_img(self, n, link_href=None, cls=None):
        src = n.get("src") or n.get("data-src")
        if not src or src.startswith("data:"):
            return
        if re.search(r"/wp-content/(themes|plugins)/", src):
            return
        r = self.fig_image(src)
        if r is None:
            return
        alt = attr_text(n.get("alt"))
        if alt.lower().startswith("thumbnail of") or alt.lower() in ("shortcut image", "map image", "initiative image", "header logo", "footer logo"):
            alt = ""
        classes = cls or n.classes
        m = ""
        if "alignleft" in classes:
            m = " media--left"
        elif "alignright" in classes:
            m = " media--right"
        self.hoist.append(self.figure(r, alt, "", m))

    def fig_image(self, src):
        u = abs_url(src)
        lp = local_path(u)
        if lp is None or "/wp-content/uploads/" not in lp:
            note("external_links", f"{self.where}: external image dropped {u}")
            return None
        return self.media.image(SITE + lp, self.img_cap)

    def figure(self, r, alt, caption, mod=""):
        wh = f' width="{r["w"]}" height="{r["h"]}"' if r.get("w") and r.get("h") else ""
        cap = f"<figcaption>{caption}</figcaption>" if caption else ""
        if self.first_img is None:
            self.first_img = (r["path"], r.get("w"), r.get("h"), alt, bool(caption))
        return f'<figure class="media{mod}"><img src="{esc_attr(r["path"])}" alt="{esc_attr(alt)}"{wh}>{cap}</figure>'

    def iframe(self, n):
        src = (n.get("src") or n.get("data-src") or "").strip()
        if src.startswith("//"):
            src = "https:" + src
        title = attr_text(n.get("title"))
        w = watch_url(src)
        if w:
            if yt_id(w):
                self.videos.append(yt_id(w))
            return f'<p class="embed"><a href="{esc_attr(w)}">{esc(title or "Video")}</a></p>'
        if src and not src.startswith("about:") and "googletagmanager" not in src:
            note("unknown_embeds", f"{self.where}: {src}")
            host = urllib.parse.urlparse(src).netloc
            return f'<p><a href="{esc_attr(src)}">{esc(title or host or src)}</a></p>'
        return ""

    # ---- blocks
    def flush_hoist(self, out, before=False):
        if self.hoist:
            out.extend(self.hoist)
            self.hoist = []

    def para(self, nodes, out, cls=None):
        self.hoist = []
        s = self.inline(nodes).strip()
        s = re.sub(r"^(<br>\s*)+|(\s*<br>)+$", "", s).strip()
        figs, self.hoist = self.hoist, []
        floats = [f for f in figs if "media--left" in f or "media--right" in f]
        flows = [f for f in figs if f not in floats]
        out.extend(floats)
        if s and not re.fullmatch(r"(<br>|\s)*", s):
            c = f' class="{cls}"' if cls else ""
            if cls == "lead":
                s = re.sub(r"</?strong>", "", s)
            out.append(f"<p{c}>{s}</p>")
        out.extend(flows)

    def children(self, n, out):
        run = []

        def flush():
            if run:
                self.para(list(run), out)
                run.clear()
        for c in n.children:
            if isinstance(c, str):
                run.append(c)
            elif c.tag in INLINE_MAP or c.tag in ("a", "span", "font", "small", "br", "img", "abbr", "mark", "code", "cite", "q", "time") and not (c.tag == "img" and False):
                if c.tag == "a" and c.find(pred=lambda x: x.tag in BLOCK and x.tag not in ("figure",)):
                    flush()
                    self.emit(c, out)
                    continue
                if c.tag == "span" and c.find(pred=lambda x: x.tag in ("div", "p", "ul", "ol", "table", "h2", "h3", "h4", "figure")):
                    flush()
                    self.children(c, out)
                    continue
                run.append(c)
            else:
                flush()
                self.emit(c, out)
        flush()

    def heading(self, n, out, level=None):
        t = n.tag
        lv = {"h1": "h2", "h2": "h2", "h3": "h3", "h4": "h4", "h5": "h4", "h6": "h4"}[t] if level is None else level
        self.hoist = []
        s = self.inline(n.children).strip()
        s = re.sub(r"^(<br>\s*)+|(\s*<br>)+$", "", s)
        s = re.sub(r"</?(strong|em)>", "", s) if lv != "h4" or True else s
        self.hoist = []
        if re.sub(r"<[^>]+>|\s", "", s):
            out.append(f"<{lv}>{s}</{lv}>")

    def emit(self, n, out):
        if isinstance(n, str):
            if n.strip():
                self.para([n], out)
            return
        t, cls = n.tag, n.classes
        if t in DROP_TAGS:
            return
        if n.get("style") and "display:none" in n.get("style", "").replace(" ", "") and not n.has("popup"):
            return
        # --- theme blocks that vanish
        if (n.has("automatic-page-title") or n.has("box-content-photo-video-gallery-footer") and not n.find(pred=lambda x: x.get("data-fancybox")) or
                n.has("footer-news-list") or n.has("last-news-container") or n.has("pagination") or n.has("scrollup") or n.has("pum") or
                n.has("archive-link") or n.has("footer-news-container") or n.has("owl-nav")):
            return
        if n.has("box-content-photo-video-gallery-footer"):
            return self.dedicated_gallery(n, out)
        if n.has("box-content-title") or n.has("page-content-title") or n.has("box-content-top-title") or n.has("box-content-top-title-variant"):
            h = n.find(pred=lambda x: x.tag in HEADINGS)
            if h:
                self.heading(h, out, "h2")
            return
        if n.has("sidebar-box") or n.has("sidebar-box-red-block") or n.has("sidebar_box_text_list_element") or n.has("sidebar-box-boxes-list") or n.has("sidebar-box-boxes-list-element"):
            return self.sidebar_box(n)
        if n.has("box-content-image-full-width-a"):
            img = n.find("img")
            if img:
                self.hoist = []
                self.hoist_img(img, cls=[c for c in img.classes if c not in ("alignleft", "alignright")])
                out.extend(self.hoist)
                self.hoist = []
            txt = n.find(cls="box-content-container-text")
            if txt:
                self.text_container(txt, out)
            return
        if n.has("box-content-mixed-one-col") or n.has("box-content-text-only-one-col"):
            c = n.find(cls="box-content-container")
            return self.text_container(c or n, out)
        if n.has("box-content-text-only-two-cols"):
            return self.text_two_cols(n, out)
        if n.has("box-content-text-only-one-col-split-cols"):
            row = n.find(cls="row") or n
            cols = [c for c in row.elements() if c.has_prefix("col-")]
            parts = []
            for c in cols:
                inner = []
                self.text_container(c, inner)
                if inner:
                    parts.append("<div>" + "".join(inner) + "</div>")
            if parts:
                out.append('<div class="cols">' + "".join(parts) + "</div>")
            return
        if n.has("box-content-linked-page-one-col") or n.has("box-content-linked-page-two-cols"):
            return self.linked_card(n, out)
        if n.has("box-content-data-map"):
            h = n.find(pred=lambda x: x.tag in HEADINGS)
            if h:
                self.heading(h, out, "h2")
            img = n.find("img")
            cap = n.find(cls="box-content-data-map-sub-title")
            if img:
                self.hoist = []
                r = self.fig_image(img.get("src"))
                if r:
                    out.append(self.figure(r, attr_text(img.get("alt")), esc(cap.text()) if cap else ""))
            return
        if n.has("contacts-tab-accordion"):
            return self.contacts(n, out)
        if n.has("accordion") and not n.has("accordion-item"):
            return self.accordion(n, out)
        if n.has("accordion-item"):
            return self.acc_item(n, out)
        if n.has("timeline-content"):
            return self.timeline(n, out)
        if n.has("wp-caption") or t == "figure":
            img = n.find("img")
            if img:
                cap = n.find(pred=lambda x: x.tag == "figcaption" or x.has("wp-caption-text"))
                r = self.fig_image(img.get("src"))
                if r:
                    mod = " media--left" if ("alignleft" in n.classes or "alignleft" in img.classes) else " media--right" if ("alignright" in n.classes or "alignright" in img.classes) else ""
                    self.hoist = []
                    capi = self.inline(cap.children).strip() if cap else ""
                    out.append(self.figure(r, attr_text(img.get("alt")), capi, mod))
                return
        # --- generic tags
        if t in HEADINGS:
            return self.heading(n, out)
        if t == "p":
            cl = "lead" if n.has("small-heading") else None
            self.para(n.children, out, cl)
            return
        if t in ("ul", "ol"):
            items = []
            for li in n.elements():
                if li.tag == "li":
                    s = self.li_content(li)
                    if s:
                        items.append(f"<li>{s}</li>")
            if items:
                out.append(f"<{t}>" + "".join(items) + f"</{t}>")
            return
        if t == "blockquote":
            inner = []
            self.children(n, inner)
            if inner:
                out.append("<blockquote>" + "".join(inner) + "</blockquote>")
            return
        if t == "table":
            return self.table(n, out)
        if t == "hr":
            out.append("<hr>")
            return
        if t == "iframe":
            s = self.iframe(n)
            if s:
                out.append(s)
            return
        if t == "img":
            self.hoist = []
            self.hoist_img(n)
            out.extend(self.hoist)
            self.hoist = []
            return
        if t in ("video", "audio"):
            note("unknown_embeds", f"{self.where}: <{t}> element dropped")
            return
        if t == "a" or t in INLINE_MAP or t in ("span", "font", "small"):
            self.para([n], out)
            return
        # transparent container (div, section, article, main, li outside lists, ...)
        self.note_unknown(n)
        self.children(n, out)

    def note_unknown(self, n):
        for c in n.classes:
            if (c.startswith(("box-content", "sidebar", "card-", "page-content", "timeline", "single-")) and not KNOWN_LAYOUT.match(c)
                    and c not in ("box-content-container", "box-content-container-text", "box-content-image", "box-content-container-link", "box-content-oembed")):
                note("unmapped", f"{self.where}: class {c}")

    def li_content(self, li):
        has_block = any(isinstance(c, Node) and c.tag in ("p", "ul", "ol", "div", "table", "blockquote", "h2", "h3", "h4", "figure") for c in li.children)
        if not has_block:
            self.hoist = []
            s = self.inline(li.children).strip()
            figs, self.hoist = self.hoist, []
            return re.sub(r"^(<br>\s*)+|(\s*<br>)+$", "", s) + "".join(figs)
        out = []
        self.children(li, out)
        return "".join(out)

    def table(self, n, out):
        rows = []
        for tr in n.find_all("tr"):
            cells = []
            for td in tr.elements():
                if td.tag not in ("td", "th"):
                    continue
                a = ""
                for k in ("colspan", "rowspan"):
                    v = td.get(k)
                    if v and v.isdigit() and v != "1":
                        a += f' {k}="{v}"'
                has_block = any(isinstance(c, Node) and c.tag in ("p", "ul", "ol", "div", "table") for c in td.children)
                if has_block:
                    inner = []
                    self.children(td, inner)
                    s = "".join(inner)
                else:
                    self.hoist = []
                    s = self.inline(td.children).strip()
                    s = re.sub(r"^(<br>\s*)+|(\s*<br>)+$", "", s)
                    self.hoist = []
                cells.append(f"<{td.tag}{a}>{s}</{td.tag}>")
            if cells:
                rows.append("<tr>" + "".join(cells) + "</tr>")
        if rows:
            out.append("<table><tbody>" + "".join(rows) + "</tbody></table>")

    def text_container(self, c, out):
        for ch in c.children:
            if isinstance(ch, str):
                if ch.strip():
                    self.para([ch], out)
                continue
            self.emit(ch, out)

    def text_two_cols(self, n, out):
        cont = n.find(cls="box-content-container")
        if cont:
            for ch in cont.children:
                if isinstance(ch, Node) and ch.has("call-to-action"):
                    continue
                self.emit(ch, out) if isinstance(ch, Node) else None
        pop = n.find(cls="box-content-container-popup")
        if pop:
            label_a = cont.find(cls="call-to-action") if cont else None
            label = label_a.text() if label_a else "Members"
            inner = pop.find(pred=lambda x: x.tag == "div" and not x.has("close") and x.find("br") is not None) or pop
            self.hoist = []
            s = self.inline(inner.children).strip()
            self.hoist = []
            s = re.sub(r"\s*(<br>\s*)+", "<br>", s)
            s = re.sub(r"^(<br>)+|(<br>)+$", "", s)
            if s:
                out.append(f'<details class="acc"><summary>{esc(label)}</summary><div class="acc-body"><p>{s}</p></div></details>')

    def accordion(self, n, out):
        for it in n.find_all(cls="accordion-item"):
            self.acc_item(it, out)

    def acc_item(self, n, out):
        head = n.find(pred=lambda x: x.has("accordion-header") or x.has("accordion-button"))
        body = n.find(cls="accordion-body")
        if not head or not body:
            return
        title = head.text()
        inner = []
        self.text_container(body, inner)
        if title:
            out.append(f'<details class="acc"><summary>{esc(title)}</summary><div class="acc-body">{"".join(inner)}</div></details>')

    def linked_card(self, n, out):
        h2 = n.find(cls="box-content-top-title")
        h2t = h2.text() if h2 else ""
        h3 = n.find("h3")
        h3t = h3.text() if h3 else ""
        txt = n.find(cls="box-content-container-text")
        ptxt = norm_text(txt.text()) if txt else ""
        link = n.find(cls="box-content-container-link")
        href = None
        for cand in ([link.find("a")] if link and link.find("a") else []) + ([h3.find("a")] if h3 and h3.find("a") else []) + n.find_all("a"):
            h = self.link(cand.get("href")) if cand is not None else None
            if h and h != "#":
                href = h
                break
        img = n.find("img")
        r = self.fig_image(img.get("src")) if img else None
        if not href:
            return
        title = h2t or h3t
        if href.startswith("/") and r:
            self.teaser_img.setdefault(href.split("#")[0], set()).add((r["path"], attr_text(img.get("alt")) if img else ""))
        imgtag = f'<img src="{esc_attr(r["path"])}" alt="" width="{r["w"]}" height="{r["h"]}">' if r and r.get("w") else (f'<img src="{esc_attr(r["path"])}" alt="">' if r else "")
        text = ptxt or (h3t if h2t else "")
        out.append(f'<ul class="cards"><li><a href="{esc_attr(href)}">{imgtag}<b>{esc(title)}</b>' + (f"<span>{esc(text)}</span>" if text else "") + "</a></li></ul>")

    def dedicated_gallery(self, n, out):
        h = n.find(pred=lambda x: x.tag in HEADINGS)
        if h and h.text():
            self.heading(h, out, "h2")
        for a in n.find_all("a", pred=lambda x: x.get("data-fancybox")):
            href = a.get("href")
            if not href:
                continue
            r = self.media.image(abs_url(href), 1280)
            if r:
                im = a.find("img")
                alt = attr_text(im.get("alt")) if im else ""
                if alt.lower().startswith("thumbnail of"):
                    alt = ""
                cap = a.find("figcaption")
                out.append(self.figure(r, alt, esc(cap.text()) if cap else ""))

    def sidebar_box(self, n):
        # teaser boxes become `related`; boxes of plain text go to the end of the body
        if n.find(cls="last-news-container"):
            return
        pages = []
        files = []
        for a in n.find_all("a"):
            h = self.link(a.get("href"))
            if not h:
                continue
            lp = local_path(h) if h.startswith("http") else h
            if h.startswith("/") and "/media/" not in h:
                pages.append(h.split("#")[0])
            elif "/media/" in h:
                files.append((a.text(), h))
        if pages:
            for im in n.find_all("img"):
                a = im.parent
                while a is not None and a.tag != "a":
                    a = a.parent
                if a is not None:
                    h = self.link(a.get("href"))
                    if h and h.startswith("/"):
                        r = self.fig_image(im.get("src"))
                        if r:
                            self.teaser_img.setdefault(h.split("#")[0], set()).add((r["path"], attr_text(im.get("alt"))))
            for p in pages:
                if p not in self.related and p != self.self_url:
                    self.related.append(p)
            return
        # text box
        title = n.find(cls="box-content-title")
        out = self.tail
        if title:
            h = title.find(pred=lambda x: x.tag in HEADINGS)
            if h:
                self.heading(h, out, "h2")
        cont = n.find(cls="box-content-container") or n
        for ch in cont.children:
            if isinstance(ch, Node) and ch.has("box-content-title"):
                continue
            self.emit(ch, out) if isinstance(ch, Node) else (self.para([ch], out) if ch.strip() else None)

    def contacts(self, n, out):
        labels = {}
        for btn in n.find_all("button", cls="nav-link"):
            tid = (btn.get("data-bs-target") or "").lstrip("#")
            labels[tid] = norm_text(btn.text())
        for pane in n.find_all(cls="tab-pane"):
            pid = pane.get("id") or ""
            rid = re.sub(r"^pills-", "", pid)
            inner = []
            for it in pane.find_all(cls="accordion-item"):
                self.acc_item(it, inner)
            if inner:
                out.append(f'<section class="region" id="{esc_attr(rid)}"><h2>{esc(labels.get(pid, rid))}</h2>' + "".join(inner) + "</section>")

    def timeline(self, n, out):
        items = []
        for box in n.find_all(cls="timeline-content-box"):
            circ = box.find(cls="timeline-content-left-circle")
            label = circ.text() if circ else ""
            right = box.find(cls="timeline-content-right") or box
            inner = []
            self.timeline_content(right, inner)
            items.append(f"<li><h3>{esc(label)}</h3>" + "".join(inner) + "</li>")
        if items:
            out.append('<ol class="timeline">' + "".join(items) + "</ol>")

    def timeline_content(self, n, out):
        for ch in n.children:
            if isinstance(ch, str):
                if ch.strip():
                    self.para([ch], out)
                continue
            if ch.has("timeline-content-table-title"):
                t = norm_text(ch.text())
                if t:
                    out.append(f"<h4>{esc(t)}</h4>")
            elif ch.tag in HEADINGS:
                self.heading(ch, out, "h4")
            elif ch.tag in ("div", "section"):
                self.timeline_content(ch, out)
            else:
                self.emit(ch, out)

    # ---- driver
    def convert(self, root, self_url=None):
        self.self_url = self_url
        out = []
        for c in root.children if isinstance(root, Node) else []:
            if isinstance(c, str):
                if c.strip():
                    self.para([c], out)
            else:
                self.emit(c, out)
        out.extend(self.tail)
        return self.finish(out)

    def finish(self, out):
        s = "\n".join(x for x in out if x)
        for _ in range(3):
            s = re.sub(r"</ul>\s*<ul class=\"cards\">", "", s)
        s = re.sub(r"<(p|li|h2|h3|h4|strong|em|u|s|sup|sub|blockquote)>\s*(<br>\s*)*</\1>", "", s)
        s = re.sub(r"<p>\s*(&nbsp;|\s)*</p>", "", s)
        s = re.sub(r"[ \t]+\n", "\n", s)
        s = re.sub(r"\n{2,}", "\n", s)
        s = re.sub(r"(<br>\s*){3,}", "<br><br>", s)
        return s.strip()


def convert_fragment(fragment, media, lang, where="", img_cap=1600, teaser_img=None):
    """Editor/REST fragment -> (html, Body)."""
    b = Body(media, lang, where, teaser_img)
    b.img_cap = img_cap
    root = parse(fragment)
    return b.convert(root), b


def drop_title_heading(body, title):
    """Remove the first heading when it repeats the page title."""
    def norm(x):
        return re.sub(r"[^\w]+", "", html.unescape(re.sub(r"<[^>]+>", "", x)).lower())
    m = re.match(r"\s*<h2>(.*?)</h2>\s*", body, re.S)
    if m and norm(m.group(1)) == norm(title):
        return body[m.end():]
    # also when preceded by a lone figure
    m = re.match(r"(\s*<figure.*?</figure>\s*)<h2>(.*?)</h2>\s*", body, re.S)
    if m and norm(m.group(2)) == norm(title):
        return m.group(1) + body[m.end():]
    return body


# ---------------------------------------------------------------- page documents


class Doc:
    """A fetched HTML page: parsed tree plus the bits the importer reads from the head and header."""

    def __init__(self, resp):
        self.status = resp["status"]
        self.final = resp["final"]
        self.text = resp["body"].decode("utf-8", "replace")
        self.root = parse(self.text) if self.status == 200 else Node("#root")
        self.main = self.root.find("main")

    def meta(self, name=None, prop=None):
        pat = (rf'<meta\s+name=["\']{name}["\']\s+content=["\']([^"\']*)["\']' if name else rf'<meta\s+property=["\']{prop}["\']\s+content=["\']([^"\']*)["\']')
        m = re.search(pat, self.text, re.I)
        return html.unescape(m.group(1)).strip() if m else ""

    def title_tag(self):
        m = re.search(r"<title>(.*?)</title>", self.text, re.S)
        return norm_text(m.group(1)) if m else ""

    def description(self):
        d = self.meta(name="description")
        return norm_text(d)

    def switcher(self):
        """{lang: path} from the header language switcher (empty when the page has none)."""
        out = {}
        box = self.root.find(cls="header-language-switch")
        if box is None:
            return out
        for a in box.find_all("a"):
            label = norm_text(a.text()).lower()
            label = label.replace("ç", "c").replace("ñ", "n")
            label = re.sub(r"[^a-z]", "", label)
            for lang, lab in LANG_LABEL.items():
                if label.startswith(lab[:4]) and label == lab:
                    p = local_path(a.get("href"))
                    if p:
                        out[lang] = with_slash(p.split("#")[0])
        return out

    def jsonld_date(self):
        m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', self.text)
        return m.group(1) if m else None

    def jsonld_modified(self):
        m = re.search(r'"dateModified"\s*:\s*"([^"]+)"', self.text)
        return m.group(1) if m else None


def lang_of_path(path):
    for l in ("it", "fr", "de", "es"):
        if path == f"/{l}" or path.startswith(f"/{l}/"):
            return l
    return "en"


def strip_prefix(path):
    l = lang_of_path(path)
    if l == "en":
        return path
    return path[len(PREFIX[l]):] or "/"


def clean_switcher(sw, own_lang, own_url, is_home=False):
    """Drop switcher entries that are only another language's home page."""
    out = {}
    for l, p in sw.items():
        if p == own_url or l == own_lang:
            out[l] = own_url if l == own_lang else p
            continue
        if not is_home and p.rstrip("/") in [PREFIX[x] or "" for x in LANGS] + [""] and p in (PREFIX[l] + "/", "/"):
            continue  # just the language home: no translation
        out[l] = p
    out[own_lang] = own_url
    return out


def trunc(text, n=300):
    text = norm_text(text)
    if len(text) <= n:
        return text
    cut = text.rfind(" ", 0, n - 1)
    return text[: cut if cut > n // 2 else n - 1].rstrip(" ,;:-") + "…"


def plain_from_html(h):
    return norm_text(re.sub(r"<[^>]+>", " ", re.sub(r"<(br|/p|/li|/h\d)>", " ", h)))


def text_excerpt(h, n=300):
    h = re.sub(r'<p class="file">.*?</p>|<p class="embed">.*?</p>|<figure.*?</figure>', " ", h, flags=re.S)
    return trunc(plain_from_html(h), n)


# ---------------------------------------------------------------- menus, footer, home


def parse_main_menu(doc, body):
    """Mega menu -> list of nodes of spec 3.4."""
    ul = doc.root.find("ul", pred=lambda n: n.get("id") == "mega-menu-main-menu")
    items = []
    if ul is None:
        return items
    for li in ul.elements():
        if li.tag != "li":
            continue
        a = next((c for c in li.elements() if c.tag == "a"), None)
        if a is None:
            continue
        node = {"title": norm_text(a.text()), "url": body.link(a.get("href"))}
        sub = next((c for c in li.elements() if c.tag == "ul"), None)
        feature, children = None, []
        if sub is not None:
            for w in sub.elements():
                cls = w.classes
                if "widget_mega_text_widget" in cls:
                    fa = w.find("h4")
                    link = fa.find("a") if fa else None
                    href = body.link((link or w.find("a") or Node("a")).get("href"))
                    img = w.find("img")
                    p = next((p for p in w.find_all("p")), None)
                    h5 = w.find("h5")
                    text = norm_text(p.text()) if p else ""
                    r = body.fig_image(img.get("src")) if img is not None else None
                    feature = {"title": norm_text(fa.text()) if fa else "", "url": href, "image": r["path"] if r else None, "text": text}
                    if h5 and h5.text():
                        feature["subtitle"] = norm_text(h5.text())
                elif "widget_mega_pagelink_widget" in cls:
                    group = None
                    for ch in w.elements():
                        if ch.tag == "h5":
                            ha = ch.find("a")
                            if ha is not None:
                                href = body.link(ha.get("href"))
                                if href:
                                    children.append({"title": norm_text(ha.text()), "url": href})
                                group = None
                            elif norm_text(ch.text()):
                                group = {"title": norm_text(ch.text()), "url": None, "children": []}
                                children.append(group)
                        elif ch.tag == "p":
                            pa = ch.find("a")
                            if pa is not None:
                                href = body.link(pa.get("href"))
                                if href:
                                    entry = {"title": norm_text(pa.text()), "url": href}
                                    (group["children"] if group else children).append(entry)
                # news widget (latest news teaser) is not stored
        children = [c for c in children if c.get("url") or c.get("children")]
        if feature and not feature.get("title"):
            feature = None
        if feature:
            node["feature"] = feature
        if children:
            node["children"] = children
        items.append(node)
    return items


def parse_footer(doc, body, main_menu):
    """Footer link columns (max two levels) and the legal links."""
    by_title = {}

    def index(nodes):
        for n in nodes:
            if n.get("url"):
                by_title.setdefault(n["title"].lower(), n["url"])
            index(n.get("children", []))
    index(main_menu)
    footer = []
    legal = []
    sec = doc.root.find(cls="footer-links")
    if sec is None:
        return footer, legal
    for h2 in sec.find_all("h2"):
        title = norm_text(h2.text()).lstrip("- ").strip()
        panel = None
        sib = h2.parent
        # the collapse div follows the h2 inside the same column
        for c in sib.elements():
            if c.tag == "div" and c.has("collapse"):
                if c.find(pred=lambda x: x.tag in ("h3",)) is not None and c.parent is sib and h2 in sib.elements():
                    idx_h = sib.elements().index(h2)
                    idx_c = sib.elements().index(c)
                    if idx_c > idx_h and (panel is None):
                        panel = c
        if panel is None:
            continue
        section = {"title": title, "url": None, "children": []}
        group = None
        first = True
        for ch in panel.elements():
            if ch.tag == "h3":
                if ch.has("first-heading"):
                    continue
                a = ch.find("a")
                if a is not None:
                    href = body.link(a.get("href"))
                    if href:
                        section["children"].append({"title": norm_text(a.text()), "url": href})
                    group = None
                else:
                    group = {"title": norm_text(ch.text()), "url": None, "children": []}
                    section["children"].append(group)
            elif ch.tag == "ul":
                for li in ch.find_all("li"):
                    a = li.find("a")
                    if a is None:
                        continue
                    t = norm_text(a.text())
                    href = body.link(a.get("href"))
                    if not href:
                        href = by_title.get(t.lower())
                    if not href:
                        note("notes", f"menus: footer link without target dropped: {t}")
                        continue
                    (group["children"] if group else section["children"]).append({"title": t, "url": href})
        section["children"] = [c for c in section["children"] if c.get("url") or c.get("children")]
        # the section that only holds contacts + policies becomes the legal list
        first_h3 = panel.find("h3", cls="first-heading")
        fa = first_h3.find("a") if first_h3 else None
        if fa is not None and section["children"] and all(c.get("url") for c in section["children"]) and re.search(r"/(contacts|contatti|contact|kontakte?|contactos)/$", body.link(fa.get("href")) or ""):
            legal = section["children"]
            continue
        if section["children"]:
            footer.append(section)
    return footer, legal


def parse_credits(doc, body):
    sec = doc.root.find(cls="footer-credits")
    out = {"name": "", "address": "", "phone": "", "email": ""}
    if sec is None:
        return out
    h2 = sec.find("h2")
    out["name"] = norm_text(h2.text()) if h2 else ""
    p = sec.find("p")
    if p is not None:
        for a in p.find_all("a"):
            m = re.search(r"email-protection#([0-9a-fA-F]+)", a.get("href"))
            if m:
                out["email"] = decode_cfemail(m.group(1))
            elif a.get("href", "").startswith("mailto:"):
                out["email"] = a.get("href")[7:]
        # lines are separated by <br>
        lines, cur = [], []
        for c in p.children:
            if isinstance(c, Node) and c.tag == "br":
                lines.append(" ".join(cur))
                cur = []
            elif isinstance(c, str):
                cur.append(c)
            elif c.tag != "a":
                cur.append(c.text())
        lines.append(" ".join(cur))
        lines = [norm_text(x) for x in lines if norm_text(x)]
        if lines:
            out["address"] = lines[0]
        if len(lines) > 1:
            out["phone"] = norm_text(lines[1].split("|")[0]).strip(" |,;")
    return out


def parse_social(doc):
    out = []
    ul = doc.root.find("ul", cls="top-header-social")
    if ul is None:
        return out
    for a in ul.find_all("a"):
        label = attr_text(a.get("aria-label"))
        href = (a.get("href") or "").strip()
        if "rss" in label.lower() or "feed" in href:
            continue
        name = re.sub(r"^(visit|visita|visitez|besuchen sie|visite)\s+(our|il nostro|la nostra|notre|nuestra|unser|unsere|nuestro)?\s*", "", label, flags=re.I)
        name = re.sub(r"\s+(page|pagina|profil|channel|canale|chaine|chaîne|kanal|seite|canal).*$", "", name, flags=re.I).strip()
        name = re.sub(r"^(la |il |nostra |notre |nuestra |la |unsere |unser )+", "", name, flags=re.I).strip()
        icon = a.find("i")
        ic = " ".join(icon.classes) if icon else ""
        for key, nm in (("facebook", "Facebook"), ("twitter", "X"), ("youtube", "YouTube"), ("instagram", "Instagram"), ("linkedin", "LinkedIn")):
            if key in ic or key in href:
                name = nm
        if href:
            out.append({"label": name or href, "url": href.strip()})
    return out


def parse_home(doc, body, lang):
    """The `home` object of spec 3.2 from a language's home page."""
    main = doc.main
    home = {}

    def img_of(node):
        im = node.find("img") if node is not None else None
        if im is None:
            return None
        r = body.fig_image(im.get("src"))
        return r["path"] if r else None

    def link_of(a):
        return body.link(a.get("href")) if a is not None else None

    works = main.find(cls="list-vertical-posts")
    if works is not None:
        h = works.find("h2")
        items = []
        for el in works.find_all(cls="sidebar-box-boxes-list-element"):
            a = el.find("h3").find("a") if el.find("h3") else None
            icon = el.find(cls="vertical-shortcuts-icon")
            photo = el.find(cls="shift-img") or (el.elements()[1] if len(el.elements()) > 1 else None)
            items.append({"title": norm_text(a.text()) if a else "", "url": link_of(a), "icon": img_of(icon), "image": img_of(photo)})
        home["works"] = {"title": norm_text(h.text()) if h else "", "items": items}
    orgs = main.find("section", cls="initiatives-blocks")
    if orgs is not None:
        h = orgs.find("h2")
        items = []
        for el in orgs.find_all(cls="initiative-block"):
            a = el.find("h3").find("a") if el.find("h3") else None
            items.append({"title": norm_text(a.text()) if a else "", "url": link_of(a), "image": img_of(el.find(cls="initiative-block-image"))})
        home["organisations"] = {"title": norm_text(h.text()) if h else "", "items": items}
    mp = main.find("section", cls="desktop-map")
    if mp is not None:
        h = mp.find("h2")
        la = mp.find(cls="home-map-link")
        a = la.find("a") if la else None
        home["map"] = {"title": norm_text(h.text()) if h else "", "image": img_of(mp.find(pred=lambda n: n.tag == "div" and n.find("img") is not None and not n.has("row") and not n.has("container-lg") and n.find("a") is None)),
                       "link": {"title": norm_text(a.text()) if a else "", "url": link_of(a)}}
    feats = []
    fb = main.find("section", cls="home-custom-boxes")
    if fb is not None:
        for col in fb.find_all(pred=lambda n: n.tag == "div" and n.has("col-lg-4") and n.find(cls="card-container") is not None):
            h2 = col.find("h2")
            a = col.find("h3").find("a") if col.find("h3") else None
            p = col.find("p")
            feats.append({"heading": norm_text(h2.text()) if h2 else "", "title": norm_text(a.text()) if a else "", "text": norm_text(p.text()) if p else "", "url": link_of(a), "image": img_of(col.find(cls="card-image"))})
    home["features"] = feats
    boxes = {}
    w = main.find(cls="small-box-around-world")
    if w is not None:
        h2, h3 = w.find("h2"), w.find("h3")
        title = " ".join(x for x in (norm_text(h2.text()) if h2 else "", norm_text(h3.text()) if h3 else "") if x)
        boxes["world"] = {"title": title, "items": [{"title": norm_text(a.text()), "url": link_of(a)} for a in w.find_all("a")]}
    st = main.find(cls="small-box-stamps")
    if st is not None:
        a = st.find("h2").find("a") if st.find("h2") else None
        boxes["philately"] = {"title": norm_text(a.text()) if a else "", "url": link_of(a), "image": img_of(st)}
    ap = main.find(cls="small-box-newsletter")
    if ap is not None:
        h2, h3 = ap.find("h2"), ap.find("h3")
        ps = ap.find_all("p")
        la = ap.find("a")
        boxes["app"] = {"title": norm_text(h2.text()) if h2 else "", "subtitle": norm_text(h3.text()) if h3 else "",
                        "text": norm_text(ps[0].text()) if ps and not ps[0].find("a") else "",
                        "link": {"title": norm_text(la.text()) if la else "", "url": link_of(la)}}
    home["boxes"] = boxes
    ln = main.find("section", cls="home-news-list")
    gl = main.find("section", cls="home-gallery")
    home["headings"] = {"latestNews": norm_text(ln.find("h2").text()) if ln is not None and ln.find("h2") else "",
                        "galleries": norm_text(gl.find("h2").text()) if gl is not None and gl.find("h2") else ""}
    return home


# ---------------------------------------------------------------- app landing page


def smart_case(s):
    s = norm_text(s)
    if len(s) > 3 and s.isupper():
        s = s.capitalize()
        s = re.sub(r"\bIos\b", "iOS", s)
        s = re.sub(r"\bApp\b", "App", s)
    return s


def convert_app(doc, body):
    root = doc.root.find(cls="app_landing")
    if root is None:
        return "", ""
    out = []
    h1 = root.find("h1")
    title = norm_text(h1.text()) if h1 else ""
    d = root.find(cls="description")
    if d is not None:
        body.para(d.children, out, "lead")
    fd = root.find(cls="features_description")
    if fd is not None:
        body.text_container(fd, out)
    stores = []
    for a in root.find_all("a"):
        href = a.get("href") or ""
        if re.search(r"apps\.apple\.com|play\.google\.com", href) and a.text():
            stores.append(f'<a class="btn" href="{esc_attr(href)}">{esc(norm_text(a.text()))}</a>')
    if stores:
        out.append("<p>" + " ".join(stores) + "</p>")
    feats = root.find(cls="features_slider")
    if feats is not None:
        for it in feats.find_all(cls="item"):
            t = it.find(cls="title")
            dd = it.find(cls="description")
            if t and t.text():
                out.append(f"<h3>{esc(smart_case(t.text()))}</h3>")
            if dd is not None:
                body.text_container(dd, out)
    faq = root.find(cls="faqs")
    if faq is not None:
        h2 = root.find("h2")
        out.append(f"<h2>{esc(norm_text(h2.text())) if h2 else 'FAQ'}</h2>")
        for it in faq.find_all(cls="faq_item"):
            q, a = it.find(cls="question"), it.find(cls="answer")
            if q and a is not None:
                inner = []
                body.text_container(a, inner)
                out.append(f'<details class="acc"><summary>{esc(norm_text(q.text()))}</summary><div class="acc-body">{"".join(inner)}</div></details>')
    bottom = root.find(cls="bottom")
    if bottom is not None:
        links = []
        for a in bottom.find_all("a"):
            href = body.link(a.get("href"))
            if href:
                links.append(f'<a class="btn" href="{esc_attr(href)}">{esc(norm_text(a.text()))}</a>')
        if links:
            out.append("<p>" + " ".join(links) + "</p>")
    note("notes", "app page: store badges, phone mock-ups and screenshots were not copied (third-party/app artwork)")
    return body.finish(out), title


# ---------------------------------------------------------------- the importer

TEMPLATES = {
    "": "default", "page-home.php": "home", "page-contacts.php": "contacts", "page-the-grand-masters.php": "timeline",
    "page-press-and-publications.php": "press-hub", "page-press-releases.php": "press-releases",
    "page-publications.php": "publications", "page-in-the-news.php": "in-the-news", "app-landing.php": "app",
}
EMPTY_BODY_TEMPLATES = {"home", "press-hub", "press-releases", "publications", "in-the-news"}
MONTHS = {
    "en": ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"],
    "it": ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"],
    "fr": ["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout", "septembre", "octobre", "novembre", "decembre"],
    "de": ["januar", "februar", "marz", "april", "mai", "juni", "juli", "august", "september", "oktober", "november", "dezember"],
    "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
}


def strip_accents(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def month_label_to_iso(label, lang):
    t = strip_accents(norm_text(label).lower())
    y = re.search(r"(\d{4})", t)
    if not y:
        return None
    for lg in [lang] + [x for x in LANGS if x != lang]:
        for i, m in enumerate(MONTHS[lg]):
            if m in t or t.startswith(m[:3] + " "):
                return f"{y.group(1)}-{i + 1:02d}"
    return None


class Importer:
    def __init__(self, args):
        self.args = args
        self.langs = [l for l in args.langs.split(",") if l in LANGS]
        self.types = [t for t in args.types.split(",") if t in TYPES_ALL]
        self.since = args.since
        self.limit = args.limit
        self.http = Http(args.workers, args.refresh)
        self.media = Media(self.http, enabled=not args.no_media)
        self.items = {"page": [], "news": [], "press": [], "gallery": []}
        self.redirects = {}
        self.known_pages = set()
        self.known_external = {}
        self.resolved = {}
        self.teaser_img = {}
        self.stats = {}
        self.menus = {}
        self.pages_rest = {}
        self.cat_terms = {}  # filled by phase categories
        self.rest_news = {}
        self.rest_cats = {}  # lang -> {term link path: {name, slug, id}}
        self.cat_map = {}
        self.collections = {}
        self.lock = threading.Lock()

    # ---- helpers
    def body_for(self, lang, where):
        b = Body(self.media, lang, where, self.teaser_img)
        b.resolver = self.resolve
        return b

    def resolve(self, path):
        """Follow a live redirect for an internal page path (menus, bodies). Returns the final path or URL."""
        base, _, frag = path.partition("#")
        if base in self.resolved:
            r = self.resolved[base]
            return r + (("#" + frag) if frag and r.startswith("/") else "")
        known = (base in self.known_pages or base in ("/",) + tuple(f"/{l}/" for l in LANGS) or
                 any(base.startswith(v[l]) for k, v in SECTIONS.items() for l in LANGS if k in ("news", "press", "galleries", "newsCategories", "galleryTypes")) or
                 re.search(r"\.\w{2,5}$", base) or base.startswith("/media/"))
        if known:
            self.resolved[base] = base
            return path
        resp = self.http.get(SITE + base)
        final = resp["final"]
        target = base
        if resp["status"] == 200:
            host = urllib.parse.urlparse(final).netloc.lower()
            if host in HOSTS:
                target = with_slash(urllib.parse.urlparse(final).path or "/")
            else:
                target = final
        if target != base:
            with self.lock:
                self.redirects[base] = target
        self.resolved[base] = target
        return target + (("#" + frag) if frag and target.startswith("/") else "")

    def posters(self, b):
        for v in dict.fromkeys(b.videos):
            self.media.poster(v)

    def cap(self, seq):
        return list(seq)[: self.limit] if self.limit else list(seq)

    def rest_list(self, route, lang, extra="", ctype=None):
        """All pages of a REST collection (cached)."""
        out, page = [], 1
        while True:
            url = f"{SITE}/wp-json/wp/v2/{route}?lang={lang}&per_page=100&page={page}{extra}"
            data, resp = self.http.json(url)
            if data is None:
                if resp["status"] not in (200, 400):
                    note("failed", f"REST {route} {lang} page {page}: HTTP {resp['status']}")
                break
            out += data
            total = int(resp.get("headers", {}).get("x-wp-totalpages", 1) or 1)
            if page >= total:
                break
            page += 1
        return out

    # ---- menus
    def phase_menus(self):
        menus = {}
        def one(lang):
            doc = Doc(self.http.get(SITE + (PREFIX[lang] or "") + "/"))
            if doc.status != 200:
                note("failed", f"home page {lang}: HTTP {doc.status}")
                return lang, None, doc
            b = self.body_for(lang, f"menus/{lang}")
            main = parse_main_menu(doc, b)
            footer, legal = parse_footer(doc, b, main)
            m = {"main": main, "footer": footer, "social": parse_social(doc), "legal": legal, "footerCredits": parse_credits(doc, b)}
            return lang, m, doc
        for lang, m, doc in self.http.map(one, self.langs):
            if m:
                menus[lang] = m
        self.menus = menus
        for lang in menus:
            REPORT["counts"].setdefault("menus", {})[lang] = sum(1 + len(n.get("children", [])) for n in menus[lang]["main"])
        return menus

    def fix_menu_urls(self):
        """Resolve aliases in menus once the page set is known."""
        def fix(nodes):
            for n in nodes:
                u = n.get("url")
                if u and u.startswith("/"):
                    r = self.resolve(u)
                    n["url"] = r
                f = n.get("feature")
                if f and f.get("url") and f["url"].startswith("/"):
                    f["url"] = self.resolve(f["url"])
                fix(n.get("children", []))
        for lang, m in self.menus.items():
            for k in ("main", "footer", "legal"):
                fix(m[k])
        return self.menus

    # ---- pages
    def phase_pages_list(self):
        for lang in self.langs:
            lst = self.rest_list("pages", lang, "&_fields=id,link,parent,menu_order,template,modified,slug,title,status")
            recs = []
            for p in lst:
                path = urllib.parse.urlparse(p["link"]).path
                if "%" in path and re.search(r"%[89a-fA-F][0-9a-fA-F]", path):
                    note("skipped_pages", f"{lang} {path}: non-Latin stray URL (spec 0)")
                    continue
                recs.append({"id": p["id"], "lang": lang, "url": with_slash(path), "parent": p.get("parent") or 0, "order": p.get("menu_order") or 0,
                             "template": p.get("template") or "", "modified": (p.get("modified") or "")[:16], "title": html.unescape(p["title"]["rendered"]).strip()})
                self.known_pages.add(with_slash(path))
            self.pages_rest[lang] = recs

    def phase_pages(self):
        work = []
        for lang in self.langs:
            recs = self.pages_rest.get(lang, [])
            if self.limit:
                home = [r for r in recs if r["template"] == "page-home.php"]
                rest = [r for r in recs if r["template"] != "page-home.php"]
                recs = home + rest[: max(0, self.limit - len(home))]
            work += recs
        self.url_by_id = {(r["lang"], r["id"]): r["url"] for l in self.langs for r in self.pages_rest.get(l, [])}
        results = self.http.map(self.build_page, work)
        for r in results:
            if r:
                self.items["page"].append(r)

    def build_page(self, rec):
        lang, url = rec["lang"], rec["url"]
        resp = self.http.get(SITE + url)
        if resp["status"] != 200:
            note("skipped_pages", f"{lang} {url}: HTTP {resp['status']}")
            return None
        doc = Doc(resp)
        fu = urllib.parse.urlparse(resp["final"])
        template = TEMPLATES.get(rec["template"], None)
        meta = {"type": "page", "lang": lang, "url": url, "title": rec["title"]}
        if fu.netloc.lower() not in HOSTS:
            meta.update({"translations": {lang: url}, "id": rec["id"], "source": SITE + url, "modified": rec["modified"], "parent": self.parent_url(rec),
                         "order": rec["order"], "template": "default", "redirect": resp["final"]})
            return {"type": "page", "lang": lang, "url": url, "meta": meta, "body": "", "sw": {}, "gkey": ("redirect", rec["template"], resp["final"])}
        final_path = with_slash(fu.path or "/")
        if final_path != url:
            with self.lock:
                self.redirects[url] = final_path
            note("skipped_pages", f"{lang} {url}: redirects to {final_path} (recorded in redirects.json)")
            return None
        if template is None:
            note("notes", f"page {url}: unknown WordPress template {rec['template']}; treated as default")
            template = "default"
        if re.search(r"/(privacy-policy|informazioni-sulla-privacy|politique-de-protection-des-donnees-personnelles|datenschutz\w*|politica-de-privacidad|cookie-policy)/$", url) or "privacy" in url.rsplit("/", 2)[-2] or "cookie" in url.rsplit("/", 2)[-2]:
            template = "privacy"
        b = self.body_for(lang, f"{lang} {url}")
        b.self_url = url
        body = ""
        extra = {}
        desc = doc.description()
        if template == "app":
            body, apptitle = convert_app(doc, b)
            if apptitle:
                meta["title"] = apptitle
        elif template == "home":
            tt = doc.title_tag()
            meta["title"] = re.split(r"\s+[-–|]\s+", tt)[0].strip() or rec["title"]
            extra["home"] = parse_home(doc, b, lang)
        elif template in EMPTY_BODY_TEMPLATES:
            body = ""
        else:
            if doc.main is None:
                note("skipped_pages", f"{lang} {url}: no <main>")
                return None
            body = b.convert(doc.main, url)
            body = drop_title_heading(body, meta["title"])
            self.posters(b)
        # lead image
        image = alt = None
        m = re.match(r'\s*<figure class="media"><img src="([^"]+)" alt="([^"]*)"[^>]*></figure>\s*', body)
        if m and template not in ("timeline",):
            image, alt = m.group(1), html.unescape(m.group(2))
            body = body[m.end():]
        sw = doc.switcher()
        if desc:
            meta["description"] = desc
        meta["translations"] = {lang: url}
        meta.update({"id": rec["id"], "source": SITE + url, "modified": rec["modified"] or None})
        if not meta["modified"]:
            del meta["modified"]
        if re.search(r"cookie", url, re.I):
            meta["status"] = "approval"
        meta["image"] = image
        if alt:
            meta["imageAlt"] = alt
        meta["parent"] = self.parent_url(rec)
        meta["order"] = rec["order"]
        meta["template"] = template
        if b.related:
            meta["related"] = [self.resolve(u) for u in b.related if u != url]
            meta["related"] = [u for i, u in enumerate(meta["related"]) if u.startswith("/") and u != url and u not in meta["related"][:i]]
            if not meta["related"]:
                del meta["related"]
        meta.update(extra)
        return {"type": "page", "lang": lang, "url": url, "meta": meta, "body": body, "sw": sw, "is_home": template == "home", "gkey": None}

    def parent_url(self, rec):
        if rec["parent"]:
            return self.url_by_id.get((rec["lang"], rec["parent"]))
        return None


    # ---- news + categories
    def phase_news_list(self):
        for lang in self.langs:
            lst = self.rest_list("notizie", lang, f"&after={self.since}T00:00:00&_fields=id,date,modified,slug,link,title,acf,news_categories")
            lst.sort(key=lambda p: p["date"], reverse=True)
            self.rest_news[lang] = self.cap(lst)
        REPORT["counts"]["news_rest_total"] = {l: len(v) for l, v in self.rest_news.items()}

    def known_cat_keys(self):
        """Keys worth carrying over: only terms whose own English URL lives under the English categories base."""
        keys = set()
        try:
            data = json.loads((CONTENT / "translations" / "categories.json").read_text(encoding="utf-8"))
        except Exception:
            return keys
        for k, c in data.items():
            u = c["terms"].get("en", {}).get("url", "")
            if u.startswith(SECTIONS["newsCategories"]["en"]):
                keys.add(k)
        return keys

    def term_info(self, path, lang):
        """name + slug of a category archive page (cached fetch)."""
        doc = Doc(self.http.get(SITE + path))
        if doc.status != 200 or doc.main is None:
            return None, None, doc
        h1 = doc.main.find("h1")
        name = norm_text(h1.text()) if h1 else ""
        return name, path.rstrip("/").rsplit("/", 1)[-1], doc

    def phase_categories(self):
        # terms seen on items, per language
        seen = {l: {} for l in LANGS}
        for lang, items in self.rest_news.items():
            for it in items:
                for t in it.get("news_categories") or []:
                    lp = with_slash(local_path(t["link"]) or "")
                    seen[lang_of_path(lp)][lp] = {"name": html.unescape(t["name"]), "slug": t["slug"]}
        en_paths = set(seen.get("en", {}))
        # parents of English terms
        for p in list(en_paths):
            parts = p.strip("/").split("/")
            for i in range(2, len(parts)):
                en_paths.add("/" + "/".join(parts[:i]) + "/")
        # English terms of other languages are found through the English archive switcher
        cats = {}
        loc_url_to_key = {}
        prev = CONTENT / "translations" / "categories.json"
        if prev.exists():  # terms of earlier runs (e.g. when English is not in --langs)
            for k, c in json.loads(prev.read_text(encoding="utf-8")).items():
                if k not in self.known_cat_keys():
                    continue
                cats[k] = c
                for l, t in c["terms"].items():
                    loc_url_to_key[t["url"]] = k
        for p in sorted(en_paths):
            name, slug, doc = self.term_info(p, "en")
            if doc.status != 200:
                continue
            parts = p.strip("/").split("/")
            parent_key = parts[-2] if len(parts) >= 3 else None
            en_name = seen["en"].get(p, {}).get("name") or name
            terms = {"en": {"name": en_name, "slug": slug, "url": p}}
            sw = doc.switcher()
            for l, lp in sw.items():
                if l == "en" or l not in self.langs:
                    continue
                lname = seen[l].get(lp, {}).get("name")
                lslug = lp.rstrip("/").rsplit("/", 1)[-1]
                if not lname:
                    n2, s2, d2 = self.term_info(lp, l)
                    lname = n2 or lslug
                terms[l] = {"name": lname, "slug": lslug, "url": lp}
            cats[slug] = {"parent": parent_key, "terms": terms}
            for l, t in terms.items():
                loc_url_to_key[t["url"]] = slug
        self.cat_map = loc_url_to_key
        # strays: localized terms on items that map to no English term
        by_name = {}
        for k, c in cats.items():
            for l, t in c["terms"].items():
                by_name.setdefault((l, strip_accents(t["name"]).lower()), set()).add(k)
        for lang in self.langs:
            for lp, t in seen[lang].items():
                if lp in self.cat_map:
                    continue
                twins = by_name.get((lang, strip_accents(t["name"]).lower()), set())
                if len(twins) == 1:
                    self.cat_map[lp] = next(iter(twins))
                    self.redirects[lp] = cats[next(iter(twins))]["terms"].get(lang, {}).get("url") or SECTIONS["news"][lang]
                    note("notes", f"category stray {lp} mapped by name to {next(iter(twins))}")
                else:
                    note("dropped_terms", f"{lang} {lp} ({t['name']})")
                    self.redirects[lp] = SECTIONS["news"][lang]
        # parent-less alias URLs (/news-categories/<slug>/ for a nested term)
        for k, c in cats.items():
            for l, t in c["terms"].items():
                alias = SECTIONS["newsCategories"][l] + t["slug"] + "/"
                if alias != t["url"]:
                    self.redirects.setdefault(alias, t["url"])
        self.categories = cats

    def news_item(self, lang, it):
        link = it["link"]
        url = with_slash(urllib.parse.urlparse(link).path)
        acf = it.get("acf") or {}
        title = html.unescape(it["title"]["rendered"]).strip()
        where = f"news {lang} {url}"
        doc = Doc(self.http.get(link))
        if doc.status != 200:
            note("failed", f"{where}: page HTTP {doc.status}")
            return None
        sw = doc.switcher()
        body, b = convert_fragment(acf.get("news_content") or "", self.media, lang, where, 1600, self.teaser_img)
        self.posters(b)
        cover = (acf.get("news_cover") or {}).get("url") if isinstance(acf.get("news_cover"), dict) else None
        meta = {"type": "news", "lang": lang, "url": url, "title": title}
        desc = doc.description()
        if desc:
            meta["description"] = desc
        meta["translations"] = {lang: url}
        meta["id"] = it["id"]
        meta["source"] = link
        meta["modified"] = date_iso(it["modified"])
        # cover + gallery details from the page
        cover_alt = credit = ""
        gal_info = {}
        if doc.main is not None:
            ci = doc.main.find(cls="box-content-single-image")
            if ci is not None:
                im = ci.find("img")
                cover_alt = attr_text(im.get("alt")) if im else ""
                fc = ci.find("figcaption")
                credit = norm_text(fc.text()) if fc else ""
            for a in doc.main.find_all("a", pred=lambda x: x.get("data-fancybox")):
                im = a.find("img")
                fc = a.find("figcaption")
                k = Media.key_for(a.get("href") or "")
                if k:
                    gal_info[k] = (attr_text(im.get("alt")) if im else "", norm_text(fc.text()) if fc else "")
        image = None
        if cover:
            r = self.media.image(cover, 1600)
            if r:
                image = r["path"]
        meta["image"] = image
        if cover_alt and image:
            meta["imageAlt"] = cover_alt
        if credit and image:
            meta["imageCredit"] = credit
        meta["date"] = date_iso(it["date"])
        meta["excerpt"] = trunc(acf.get("news_excerpt") or "", 300) or text_excerpt(body)
        gallery = []
        for el in acf.get("news_gallery_elements") or []:
            u = el.get("url") if isinstance(el, dict) else None
            if not u:
                continue
            r = self.media.image(u, 1280)
            if r:
                alt, cap = gal_info.get(Media.key_for(u) or "", ("", ""))
                if alt == title:
                    alt = ""
                gallery.append({"src": r["path"], "w": r["w"], "h": r["h"], "alt": alt, "caption": cap})
        if gallery:
            meta["gallery"] = gallery
        vid = acf.get("news_video")
        if vid:
            frag = parse(vid)
            ifr = frag.find("iframe")
            w = watch_url(ifr.get("src")) if ifr is not None else watch_url(vid)
            if w:
                meta["video"] = w
                if yt_id(w):
                    self.media.poster(yt_id(w))
            else:
                note("unknown_embeds", f"{where}: news_video {vid[:120]}")
        sub = norm_text(re.sub(r"<[^>]+>", " ", html.unescape(acf.get("sub_title") or "")))
        if sub:
            meta["subtitle"] = sub
        keys = []
        for t in it.get("news_categories") or []:
            lp = with_slash(local_path(t["link"]) or "")
            k = self.cat_map.get(lp)
            if k and k not in keys:
                keys.append(k)
        meta["categories"] = keys or ["all-news"]
        if acf.get("cover_image_copyrighted") is True:
            meta["imageCopyrighted"] = True
        return {"type": "news", "lang": lang, "url": url, "meta": meta, "body": body, "sw": sw, "slug": urllib.parse.urlparse(link).path.strip("/").rsplit("/", 1)[-1]}

    def phase_news(self):
        work = [(l, it) for l in self.langs for it in self.rest_news.get(l, [])]
        for r in self.http.map(lambda a: self.news_item(*a), work):
            if r:
                self.items["news"].append(r)

    # ---- listings: press releases and galleries
    def walk_listing(self, lang, base, card_fn, cut="default"):
        cut = self.since if cut == "default" else cut
        out, n = [], 1
        while True:
            url = SITE + base + ("" if n == 1 else f"page/{n}/")
            resp = self.http.get(url)
            if resp["status"] != 200:
                break
            doc = Doc(resp)
            if doc.main is None:
                break
            cards = card_fn(doc)
            if not cards:
                break
            out += cards
            dates = [c["date"] for c in cards if c.get("date")]
            if cut and dates and max(dates) < cut:
                break
            if self.limit and len([c for c in out if (c.get("date") or "9") >= (cut or "")]) >= self.limit:
                break
            pg = doc.main.find(cls="pages")
            total = 1
            if pg is not None:
                m = re.search(r"(\d+)\s*\D+\s*(\d+)\s*$", pg.text())
                if m:
                    total = int(m.group(2))
            if n >= total:
                break
            n += 1
        return [c for c in out if (c.get("date") or "9") >= (cut or "")][: self.limit or None]

    @staticmethod
    def press_cards(doc):
        cards = []
        for c in doc.main.find_all(cls="card-container"):
            h = c.find("h2")
            a = h.find("a") if h else None
            if a is None:
                continue
            vals = [norm_text(td.text()) for td in c.find_all("td")]
            date = next((dmy_to_iso(v) for v in vals if dmy_to_iso(v)), None)
            cards.append({"url": with_slash(local_path(a.get("href")) or ""), "title": norm_text(a.text()), "date": date, "org": vals[1] if len(vals) > 1 else "", "lang_label": vals[3] if len(vals) > 3 else ""})
        return cards

    @staticmethod
    def gallery_cards(doc):
        cards = []
        for c in doc.main.find_all(cls="card-container"):
            h = c.find("h2")
            a = h.find("a") if h else None
            if a is None:
                continue
            ds = c.find(cls="card-date")
            icon = c.find(cls="card-icon")
            kind = "photo"
            if icon is not None:
                cl = set(icon.classes)
                kind = "video" if "video" in cl else "album" if "gallery" in cl else "photo"
            cards.append({"url": with_slash(local_path(a.get("href")) or ""), "title": norm_text(a.text()), "date": dmy_to_iso(ds.text()) if ds else None, "kind": kind})
        return cards

    def phase_press(self):
        work = []
        for lang in self.langs:
            cards = self.walk_listing(lang, SECTIONS["pressList"][lang], self.press_cards)
            work += [(lang, c) for c in cards]
        for r in self.http.map(lambda a: self.press_item(*a), work):
            if r:
                self.items["press"].append(r)

    def press_item(self, lang, card):
        url = card["url"]
        where = f"press {lang} {url}"
        resp = self.http.get(SITE + url)
        if resp["status"] != 200:
            note("failed", f"{where}: HTTP {resp['status']}")
            return None
        doc = Doc(resp)
        fu = with_slash(urllib.parse.urlparse(resp["final"]).path)
        if fu != url:
            self.redirects[url] = fu
            url = fu
        h1 = doc.main.find("h1") if doc.main else None
        title = norm_text(h1.text()) if h1 else card["title"]
        metabox = doc.main.find(cls="box-content-meta") if doc.main else None
        org = card.get("org", "")
        if metabox is not None:
            divs = metabox.find_all("div")
            for d in divs:
                sp = d.find("span")
                lab = norm_text(sp.text()).rstrip(":").lower() if sp else ""
                val = norm_text(d.text())
                if sp:
                    val = norm_text(val[len(norm_text(sp.text())):])
                if lab.startswith(("organ", "organi", "organis")) and val:
                    org = val
            parent = metabox.parent
            idx = parent.children.index(metabox)
            container = Node("div")
            container.children = parent.children[idx + 1:]
        else:
            container = Node("div")
        b = self.body_for(lang, where)
        b.self_url = url
        body = b.convert(container, url)
        body = drop_title_heading(body, title)
        self.posters(b)
        dt = doc.jsonld_date()
        date = utc_to_local(dt) or (card["date"] + "T00:00" if card.get("date") else None)
        if date and card.get("date") and date[:10] != card["date"]:
            date = card["date"] + "T" + date[11:]
        meta = {"type": "press", "lang": lang, "url": url, "title": title}
        d = doc.description()
        if d:
            meta["description"] = d
        meta["translations"] = {lang: url}
        meta["source"] = SITE + url
        mod = utc_to_local(doc.jsonld_modified())
        if mod:
            meta["modified"] = mod
        meta["image"] = None
        meta["date"] = date
        meta["excerpt"] = text_excerpt(body)
        meta["organisation"] = org
        return {"type": "press", "lang": lang, "url": url, "meta": meta, "body": body, "sw": doc.switcher(), "slug": url.strip("/").rsplit("/", 1)[-1]}

    def phase_galleries(self):
        work = []
        for lang in self.langs:
            cards = self.walk_listing(lang, SECTIONS["galleries"][lang], self.gallery_cards)
            work += [(lang, c) for c in cards]
        for r in self.http.map(lambda a: self.gallery_item(*a), work):
            if r:
                self.items["gallery"].append(r)

    def gallery_item(self, lang, card):
        url = card["url"]
        where = f"gallery {lang} {url}"
        resp = self.http.get(SITE + url)
        if resp["status"] != 200:
            note("failed", f"{where}: HTTP {resp['status']}")
            return None
        doc = Doc(resp)
        fu = with_slash(urllib.parse.urlparse(resp["final"]).path)
        if fu != url:
            self.redirects[url] = fu
            url = fu
        main = doc.main
        h1 = main.find("h1") if main else None
        title = norm_text(h1.text()) if h1 else card["title"]
        kind = card.get("kind", "photo")
        photos, video = [], None
        gal = main.find(cls="box-content-single-gallery") if main else None
        vbox = main.find(cls="box-content-single-gallery-video") if main else None
        if vbox is not None:
            ifr = vbox.find("iframe")
            if ifr is not None:
                video = watch_url(ifr.get("src"))
                if not video:
                    note("unknown_embeds", f"{where}: {ifr.get('src')}")
            kind = "video"
        seen = set()
        if gal is not None:
            for im in gal.find_all("img"):
                src = im.get("src")
                k = Media.key_for(src or "")
                if not k or k in seen:
                    continue
                seen.add(k)
                r = self.media.image(src, 1280)
                if r:
                    alt = attr_text(im.get("alt"))
                    photos.append({"src": r["path"], "w": r["w"], "h": r["h"], "alt": "" if alt == title else alt, "caption": ""})
        if kind == "photo" and len(photos) > 1:
            kind = "album"
        data = main.find(cls="box-content-single-data") if main else None
        body = ""
        b = self.body_for(lang, where)
        if data is not None:
            c = Node("div")
            c.children = [x for x in data.children if not (isinstance(x, Node) and x.has("card-date"))]
            body = b.convert(c, url)
        dt = doc.jsonld_date()
        date = utc_to_local(dt) or (card["date"] + "T00:00" if card.get("date") else None)
        if date and card.get("date") and date[:10] != card["date"]:
            date = card["date"] + "T" + date[11:]
        meta = {"type": "gallery", "lang": lang, "url": url, "title": title}
        d = doc.description()
        if d:
            meta["description"] = d
        meta["translations"] = {lang: url}
        meta["source"] = SITE + url
        mod = utc_to_local(doc.jsonld_modified())
        if mod:
            meta["modified"] = mod
        image = photos[0]["src"] if photos else None
        if video and yt_id(video):
            if self.media.poster(yt_id(video)) or (MEDIA_DIR / "embeds" / f"youtube-{yt_id(video)}.webp").exists():
                image = f"/media/embeds/youtube-{yt_id(video)}.webp"
        meta["image"] = image
        meta["date"] = date
        meta["excerpt"] = text_excerpt(body) if body else ""
        if photos:
            meta["gallery"] = photos
        if video:
            meta["video"] = video
        meta["kind"] = kind
        return {"type": "gallery", "lang": lang, "url": url, "meta": meta, "body": body, "sw": doc.switcher(), "slug": url.strip("/").rsplit("/", 1)[-1]}


    # ---- collections
    def phase_collections(self):
        for lang in self.langs:
            recs = self.pages_rest.get(lang, [])
            pub = next((r for r in recs if r["template"] == "page-publications.php"), None)
            itn = next((r for r in recs if r["template"] == "page-in-the-news.php"), None)
            if pub:
                self.collections[(lang, "publications")] = self.publications(lang, pub)
            if itn:
                self.collections[(lang, "in-the-news")] = self.in_the_news(lang, itn)

    @staticmethod
    def pub_cards(doc):
        cards = []
        for c in doc.main.find_all(cls="card-container"):
            h2 = c.find("h2")
            if h2 is None:
                continue
            cd = c.find(cls="card-publications")
            p = cd.find("p") if cd is not None else None
            img = c.find("img")
            files = []
            for a in c.find_all("a"):
                if a.get("href") and a.parent is not None and a.parent.tag == "li":
                    files.append((norm_text(a.text()), a.get("href")))
            cards.append({"title": norm_text(h2.text()), "label": norm_text(p.text()) if p else "", "img": img.get("src") if img is not None else None, "files": files})
        return cards

    def publications(self, lang, page):
        base = page["url"]
        b = self.body_for(lang, f"publications {lang}")
        doc = Doc(self.http.get(SITE + base))
        title = norm_text(doc.main.find("h1").text()) if doc.main is not None and doc.main.find("h1") else page["title"]
        cats = []
        if doc.main is not None:
            tl = doc.main.find(cls="page-content-top-links")
            if tl is not None:
                for a in tl.find_all("a"):
                    u = with_slash(local_path(a.get("href")) or "")
                    cats.append({"key": u.strip("/").rsplit("/", 1)[-1], "title": norm_text(a.text()), "url": u})
        cat_of = {}
        for c in cats:
            for card in self.walk_listing(lang, c["url"], self.pub_cards, cut=None):
                cat_of.setdefault((card["title"], card["label"]), c["key"])
        items = []
        for card in self.walk_listing(lang, base, self.pub_cards, cut=None):
            r = self.media.image(card["img"], 1600) if card["img"] else None
            date = month_label_to_iso(card["label"], lang)
            archive = bool(date and date < self.since[:7])
            files = []
            for label, href in card["files"]:
                if archive:
                    # documents older than --since are not copied (size); the live file stays linked until the archive import
                    lp = local_path(href)
                    loc = (SITE + lp) if lp else href
                    with _report_lock:
                        REPORT["counts"]["publication_files_left_live"] = REPORT["counts"].get("publication_files_left_live", 0) + 1
                else:
                    loc = b.link(href)
                if loc:
                    files.append({"label": label, "url": loc})
            it = {"title": card["title"], "date": date, "dateLabel": card["label"], "image": r["path"] if r else None,
                  "category": cat_of.get((card["title"], card["label"])), "files": files}
            if not it["date"]:
                del it["date"]
            items.append(it)
        return {"url": base, "title": title, "categories": cats, "items": items}

    @staticmethod
    def news_cuttings(doc):
        cards = []
        for c in doc.main.find_all(cls="card-container"):
            h2 = c.find("h2")
            a = h2.find("a") if h2 else None
            if a is None:
                continue
            vals = [norm_text(td.text()) for td in c.find_all("td")]
            ex = c.find(cls="card-excerpt")
            date = next((dmy_to_iso(v) for v in vals if dmy_to_iso(v)), None)
            cards.append({"title": norm_text(a.text()), "url": (a.get("href") or "").strip(), "agency": vals[1] if len(vals) > 1 else "",
                          "language": vals[3] if len(vals) > 3 else "", "date": date, "excerpt": norm_text(ex.text()) if ex is not None else ""})
        return cards

    def in_the_news(self, lang, page):
        base = page["url"]
        doc = Doc(self.http.get(SITE + base))
        title = norm_text(doc.main.find("h1").text()) if doc.main is not None and doc.main.find("h1") else page["title"]
        cards = self.walk_listing(lang, base, self.news_cuttings)
        items = [{"title": c["title"], "url": c["url"], "agency": c["agency"], "language": c["language"], "date": c["date"], "excerpt": c["excerpt"]} for c in cards]
        return {"url": base, "title": title, "items": items}

    # ---- translation groups
    def build_groups(self):
        index = {}
        for typ, items in self.items.items():
            for it in items:
                index[(typ, it["url"])] = it
        parent = {k: k for k in index}

        def find(k):
            while parent[k] != k:
                parent[k] = parent[parent[k]]
                k = parent[k]
            return k

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra
        dropped = 0
        for (typ, url), it in index.items():
            homes = {"/"} | {PREFIX[x] + "/" for x in LANGS if PREFIX[x]}
            for l, p in it.get("sw", {}).items():
                if l == it["lang"]:
                    continue
                if p in homes and not it.get("is_home"):
                    continue  # a language switcher entry that only points at that language's home: no translation
                if (typ, p) in index:
                    union((typ, url), (typ, p))
                else:
                    dropped += 1
            if it.get("gkey"):
                for (t2, u2), o in index.items():
                    if o.get("gkey") == it["gkey"] and o["lang"] != it["lang"]:
                        union((typ, url), (t2, u2))
        groups = {}
        for k in index:
            groups.setdefault(find(k), []).append(k)
        for members in groups.values():
            tr = {}
            for typ, url in sorted(members, key=lambda k: LANGS.index(index[k]["lang"])):
                l = index[(typ, url)]["lang"]
                if l in tr:
                    note("notes", f"translation conflict: two {l} members in one group ({tr[l]} and {url}); kept the first")
                    continue
                tr[l] = url
            for typ, url in members:
                it = index[(typ, url)]
                it["meta"]["translations"] = {l: tr[l] for l in LANGS if l in tr}
                it["group_size"] = len(tr)
        REPORT["counts"]["translation_targets_not_imported"] = dropped
        return index

    # ---- write
    def page_file(self, it):
        lang, url = it["lang"], it["url"]
        rel = strip_prefix(url).strip("/")
        segs = [re.sub(r"[^A-Za-z0-9._-]", "-", urllib.parse.unquote(s)) for s in rel.split("/") if s]
        d = CONTENT / "pages" / lang
        for s in segs:
            d = d / s
        return d / "index.html" if segs else CONTENT / "pages" / lang / "index.html"

    def dated_file(self, typ, it):
        folder = {"news": "news", "press": "press", "gallery": "galleries"}[typ]
        year = it["meta"]["date"][:4]
        return CONTENT / folder / it["lang"] / year / (file_slug(it["slug"]) + ".html")

    KEYS = ["type", "lang", "url", "title", "description", "translations", "id", "source", "modified", "imported", "status", "image", "imageAlt", "imageCredit",
            "date", "excerpt", "gallery", "video", "subtitle", "categories", "imageCopyrighted", "organisation", "kind",
            "parent", "order", "template", "related", "redirect", "home"]

    def ordered(self, meta):
        out = {k: meta[k] for k in self.KEYS if k in meta}
        for k, v in meta.items():
            if k not in out:
                out[k] = v
        return out

    def register_teasers(self):
        for lang, m in self.menus.items():
            for n in m["main"]:
                f = n.get("feature")
                if f and f.get("url") and f.get("image") and f["url"].startswith("/"):
                    self.teaser_img.setdefault(f["url"].split("#")[0], set()).add((f["image"], ""))
        for it in self.items["page"]:
            home = it["meta"].get("home")
            if not home:
                continue
            for grp in ("works", "organisations"):
                for x in (home.get(grp) or {}).get("items", []):
                    if x.get("url", "").startswith("/") and x.get("image"):
                        self.teaser_img.setdefault(x["url"].split("#")[0], set()).add((x["image"], ""))
            for x in home.get("features", []):
                if x.get("url", "").startswith("/") and x.get("image"):
                    self.teaser_img.setdefault(x["url"].split("#")[0], set()).add((x["image"], ""))
            ph = (home.get("boxes") or {}).get("philately")
            if ph and ph.get("url", "").startswith("/") and ph.get("image"):
                self.teaser_img.setdefault(ph["url"].split("#")[0], set()).add((ph["image"], ""))

    def finalize(self):
        self.register_teasers()
        index = self.build_groups()
        # group-wide settings for pages
        pages = self.items["page"]
        url_set = {(it["lang"], it["url"]) for it in pages}
        by_url = {it["url"]: it for it in pages}
        # privacy / cookie policy templates and approval status travel with the translation group
        groups = {}
        for it in pages:
            groups.setdefault(tuple(sorted(it["meta"]["translations"].items())), []).append(it)
        for members in groups.values():
            if any(re.search(r"^/(privacy-policy|cookie-policy)/$", m["url"]) for m in members):
                cookie = any(m["url"] == "/cookie-policy/" for m in members)
                for m in members:
                    m["meta"]["template"] = "privacy"
                    if cookie:
                        m["meta"]["status"] = "approval"
                    elif m["meta"].get("status") == "approval":
                        del m["meta"]["status"]
        for it in pages:
            m = it["meta"]
            if not m.get("image") and not m.get("redirect"):
                cands = self.teaser_img.get(it["url"])
                t = min(cands) if cands else None
                if t:
                    m["image"] = t[0]
                    if t[1]:
                        m["imageAlt"] = t[1]
            if "related" in m:
                rel = []
                for u in m["related"]:
                    if (it["lang"], u) in url_set and u != it["url"] and u not in rel:
                        rel.append(u)
                if rel:
                    m["related"] = rel
                else:
                    del m["related"]
            if m.get("parent") and (it["lang"], m["parent"]) not in url_set:
                pass
        # redirects of pages dropped because they redirect inside the site: use the same language's target
        fixed = {}
        for src, dst in self.redirects.items():
            if dst.startswith("/") and lang_of_path(src) != "en" and lang_of_path(dst) == "en":
                tgt = by_url.get(dst)
                tl = tgt["meta"]["translations"].get(lang_of_path(src)) if tgt else None
                if tl:
                    dst = tl
            fixed[src] = dst
        self.redirects = fixed
        # write files
        for typ, items in self.items.items():
            st = self.stats.setdefault(typ, {})
            for it in items:
                it["meta"]["imported"] = True
                meta = self.ordered(it["meta"])
                path = self.page_file(it) if typ == "page" else self.dated_file(typ, it)
                write_content(path, meta, it["body"], st)
                REPORT["counts"].setdefault(typ, {})
                REPORT["counts"][typ][it["lang"]] = REPORT["counts"][typ].get(it["lang"], 0) + 1
                if it.get("group_size", 1) < 2 and not it["meta"].get("redirect") and not it.get("is_home") and not (typ == "page" and it["meta"].get("template") == "app"):
                    note("no_translation", f"{typ} {it['lang']} {it['url']}")

    def write_menus(self):
        path = CONTENT / "menus.json"
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        for lang, m in self.menus.items():
            data[lang] = m
        data = {l: data[l] for l in LANGS if l in data}
        write_text_if_changed(path, json.dumps(data, ensure_ascii=False, indent=1) + "\n")

    def write_categories(self):
        path = CONTENT / "translations" / "categories.json"
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        for k, c in self.categories.items():
            old = data.get(k)
            if old:
                old["terms"].update(c["terms"])
                old["parent"] = c["parent"]
            else:
                data[k] = c
        write_text_if_changed(path, json.dumps(data, ensure_ascii=False, indent=1) + "\n")
        REPORT["counts"]["categories"] = len(data)

    def write_collections(self):
        for (lang, name), data in self.collections.items():
            path = CONTENT / "collections" / lang / f"{name}.json"
            write_text_if_changed(path, json.dumps(data, ensure_ascii=False, indent=1) + "\n")
            REPORT["counts"].setdefault(name, {})[lang] = len(data["items"])

    def add_category_sitemap_redirects(self):
        """Walk the live news_categories sitemap: every term must be a category page or a redirect."""
        r = self.http.get(SITE + "/news_categories-sitemap.xml")
        if r["status"] != 200:
            note("notes", "news_categories sitemap not readable; category redirects not completed")
            return
        paths = [urllib.parse.unquote(urllib.parse.urlsplit(u).path)
                 for u in re.findall(r"<loc>([^<]+)</loc>", r["body"].decode("utf-8", "replace"))]
        known = set(self.redirects)
        known.update(x["from"] for x in (json.loads((CONTENT / "redirects.json").read_text(encoding="utf-8")) if (CONTENT / "redirects.json").exists() else []))
        news_base = {l: SECTIONS["news"][l] for l in LANGS}
        self.redirects.update(category_sitemap_redirects(paths, self.categories, known, news_base))

    def write_redirects(self):
        path = CONTENT / "redirects.json"
        old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        merged = {r["from"]: r["to"] for r in old}
        for src, dst in self.redirects.items():
            if src != dst:
                merged[src] = dst
        # document uploads -> /media/
        for key, v in self.media.map.items():
            p = v.get("path")
            if p and not key.startswith("yt-poster") and p.rsplit(".", 1)[-1].lower() in DOC_EXT:
                merged["/wp-content/uploads/" + urllib.parse.quote(key)] = urllib.parse.quote(p, safe="/%")
        data = [{"from": k, "to": merged[k]} for k in sorted(merged)]
        write_text_if_changed(path, json.dumps(data, ensure_ascii=False, indent=1) + "\n")
        REPORT["counts"]["redirects"] = len(data)



def category_sitemap_redirects(paths, cats, known, news_base):
    """Redirects for live news-category URLs that are not a term of categories.json.
    paths: URL paths of the live news_categories sitemap; cats: categories.json; known: URLs that already
    resolve or redirect; news_base: {lang: news listing}. Duplicate terms ('-2') go to their twin, others to the
    same-slug term, the parent term, or the language's news listing."""
    term_urls, by_slug = set(), {}
    for c in cats.values():
        for l, t in c["terms"].items():
            term_urls.add(t["url"])
            by_slug.setdefault((l, t["slug"]), t["url"])
    out = {}
    for path in paths:
        path = with_slash(path)
        if path in term_urls or path in known:
            continue
        lang = lang_of_path(path)
        parts = [x for x in path.strip("/").split("/") if x]
        leaf = parts[-1] if parts else ""
        stem = re.sub(r"-\d+$", "", leaf)
        target = by_slug.get((lang, leaf)) or by_slug.get((lang, stem))
        if not target:
            for k in range(len(parts) - 1, 0, -1):
                up = "/" + "/".join(parts[:k]) + "/"
                if up in term_urls:
                    target = up
                    break
        out[path] = target or news_base[lang]
    return out


def media_total():
    total = 0
    n = 0
    for p in MEDIA_DIR.rglob("*"):
        if p.is_file():
            total += p.stat().st_size
            n += 1
    return n, total


def print_report(imp, started):
    print("\n===== import report =====")
    for k, v in REPORT["counts"].items():
        print(f"{k}: {v}")
    for typ, st in imp.stats.items():
        print(f"files {typ}: {st}")
    for key, title in (("no_translation", "items without a translation group"), ("dropped_terms", "dropped category terms"), ("skipped_files", "skipped or oversized files"),
                       ("unknown_embeds", "unknown embeds"), ("unmapped", "unmapped markup (class seen)"), ("skipped_pages", "skipped pages"),
                       ("external_links", "links/images left external"), ("notes", "notes"), ("failed", "failed requests")):
        vals = REPORT[key]
        uniq = sorted(set(vals))
        print(f"{title}: {len(vals)}")
        for v in uniq[:25]:
            print("  -", v)
        if len(uniq) > 25:
            print(f"  ... {len(uniq) - 25} more")
    n, total = media_total()
    print(f"media: {n} files, {total / 1048576:.1f} MB in static/media")
    print(f"network requests: {imp.http.network_requests}; elapsed {time.time() - started:.0f}s")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", default="2025-01-01")
    ap.add_argument("--langs", default=",".join(LANGS))
    ap.add_argument("--types", default=",".join(TYPES_ALL))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-media", action="store_true")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    _self_test()
    for k in REPORT:
        REPORT[k].clear() if isinstance(REPORT[k], list) else REPORT[k].clear()
    if args.self_test:
        print("self-test ok")
        return 0
    started = time.time()
    imp = Importer(args)
    types = imp.types
    try:
        imp.phase_pages_list()
        imp.redirects["/en/contact/"] = "/contacts/"
        if "menus" in types:
            imp.phase_menus()
            imp.fix_menu_urls()
        if "pages" in types:
            imp.phase_pages()
        if "news" in types or "categories" in types:
            imp.phase_news_list()
            imp.phase_categories()
            if "news" not in types:
                imp.rest_news = {}
        if "news" in types:
            imp.phase_news()
        if "press" in types:
            imp.phase_press()
        if "galleries" in types:
            imp.phase_galleries()
        if "collections" in types:
            imp.phase_collections()
        imp.finalize()
        if "menus" in types:
            imp.write_menus()
        if "news" in types or "categories" in types:
            imp.write_categories()
        if "collections" in types:
            imp.write_collections()
        if "news" in types or "categories" in types:
            imp.add_category_sitemap_redirects()
        imp.write_redirects()
    finally:
        imp.media.save()
    print_report(imp, started)
    return 0


# ---------------------------------------------------------------- self test (no network)


def _self_test():
    assert file_slug("Caf%C3%A9 Order/Ünit 2026!") == "caf--order--nit-2026-", file_slug("Caf%C3%A9 Order/Ünit 2026!")
    assert len(file_slug("a" * 300)) == 120
    key = 0x2B
    addr = "info@orderofmalta.int"
    enc = f"{key:02x}" + "".join(f"{ord(c) ^ key:02x}" for c in addr)
    assert decode_cfemail(enc) == addr
    assert strip_size_suffix("2026/11/photo-1600x852.jpg") == "2026/11/photo.jpg"
    assert strip_size_suffix("2026/11/photo-scaled.jpeg") == "2026/11/photo.jpeg"
    assert strip_size_suffix("2026/11/photo-e1699870960228.png") == "2026/11/photo.png"
    assert strip_size_suffix("2026/11/photo-1024x640-scaled.jpg") == "2026/11/photo.jpg"
    assert strip_size_suffix("2026/11/a-b.jpg") == "2026/11/a-b.jpg"
    assert media_name("2026/11/Some File (1).JPG") == "2026/11/some-file-1-.jpg" or media_name("2026/11/Some File (1).JPG").startswith("2026/11/some-file-1")
    assert dmy_to_iso("02/11/2026") == "2026-11-02" and dmy_to_iso("x") is None
    assert utc_to_local("2026-11-09T14:31:02+00:00") == "2026-11-09T16:31"
    assert month_label_to_iso("July 2026", "en") == "2026-07" and month_label_to_iso("Juli 2026", "de") == "2026-07"
    assert local_path("https://www.orderofmalta.int/a/b") == "/a/b" and local_path("https://smom/x/") == "/x/" and local_path("https://example.org/") is None
    assert with_slash("/a/b") == "/a/b/" and with_slash("/a/b.pdf") == "/a/b.pdf" and with_slash("/a#x") == "/a/#x"
    assert lang_of_path("/it/x/") == "it" and strip_prefix("/fr/x/") == "/x/" and lang_of_path("/italy/") == "en"
    # front matter round trip
    meta = {"type": "news", "title": "Ünï ‘q’", "date": "2026-11-09T16:31", "imported": True, "categories": ["all-news"]}
    text = dump_front(meta, "<p>x</p>")
    assert split_front(text) == (meta, "<p>x</p>\n"), split_front(text)
    # body normalisation samples (no media access needed)
    class _NoMedia:
        enabled = False

        def image(self, *a, **k):
            return None

        def document(self, *a, **k):
            return None

        def poster(self, *a, **k):
            return False
    nm = _NoMedia()
    html_in = ('<div class="row"><div class="col-12"><p class="small-heading"><strong>Lead</strong></p>'
               '<p style="x" onclick="a()">A <b>B</b> <span style="color:red">C</span><script>evil()</script></p>'
               '<p><a href="https://www.orderofmalta.int/about-the-order-of-malta/mission">m</a> <a href="/cdn-cgi/l/email-protection#' + enc + '">[email protected]</a>'
               ' <a href="www.example.org">w</a> <a href="javascript:x()">j</a></p>'
               '<iframe title="Vid" src="https://www.youtube.com/embed/B3HY0f6sw0I?feature=oembed"></iframe>'
               '<iframe src="https://example.org/x"></iframe>'
               '<ul><li>one</li><li><p>two</p></li></ul><h1>T</h1><h5>S</h5><table class="x"><tr><td colspan="2">c</td></tr></table>'
               '<div class="accordion-item"><h2 class="accordion-header"><button>Q?</button></h2><div class="accordion-body"><p>A.</p></div></div>'
               '</div></div>')
    out, b = convert_fragment(html_in, nm, "en", "selftest")
    assert '<p class="lead">Lead</p>' in out, out
    for bad in ("style=", "onclick", "<script", "<iframe", "class=\"row\"", "col-12", "javascript:", "<h1"):
        assert bad not in out, (bad, out)
    assert "<p>A <strong>B</strong> C</p>" in out, out
    assert 'href="/about-the-order-of-malta/mission/"' in out, out
    assert 'href="mailto:info@orderofmalta.int"' in out, out
    assert 'href="https://www.example.org"' in out, out
    assert '<p class="embed"><a href="https://www.youtube.com/watch?v=B3HY0f6sw0I">Vid</a></p>' in out, out
    assert '<p><a href="https://example.org/x">example.org</a></p>' in out, out
    assert '<td colspan="2">c</td>' in out and "<h2>T</h2>" in out and "<h4>S</h4>" in out, out
    assert '<details class="acc"><summary>Q?</summary><div class="acc-body"><p>A.</p></div></details>' in out, out
    assert drop_title_heading("<h2>Mission</h2><p>x</p>", "Mission") == "<p>x</p>"
    # unclosed heading inside a sidebar box must not swallow the box
    root = parse('<div class="sidebar-box"><div class="box-content-title"><h2>Hospitaller mission</div><div class="x"><p>after</p></div></div>')
    h2 = root.find("h2")
    assert h2.text() == "Hospitaller mission", h2.text()
    assert trunc("word " * 100, 50).endswith("…") and len(trunc("word " * 100, 50)) <= 50


if __name__ == "__main__":
    sys.exit(main())
