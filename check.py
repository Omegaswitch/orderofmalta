#!/usr/bin/env python3
"""Checks the built site in dist/. Run after build.py; exits non-zero on any failure.

    python3 build.py --offline && python3 check.py

Set CHECK_DIST to check another built folder (used for testing against fixtures).
"""
import json
import os
import posixpath
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent
DIST = Path(os.environ.get("CHECK_DIST") or ROOT / "dist")
sys.path.insert(0, str(ROOT / "tools"))

LANGS = ("en", "it", "fr", "de", "es")
OWN_HOSTS = {"www.orderofmalta.int", "orderofmalta.int"}
HOME_PAGES = ("index.html", "it/index.html", "fr/index.html", "de/index.html", "es/index.html")

# Only these official emblem/brand files may appear under /img/; anything else is a new, unapproved mark.
BRAND_FILES = re.compile(r"^/img/(emblems/armorial-bearing-(420|840)\.webp|banner/banner-photo\.webp|og-(en|it|fr|de|es)\.jpg|lockup/(shield|en|it|fr|de|es)\.svg|favicon/[\w.-]+)$")
# The communications policy forbids the acronym; legacy texts are flagged, not rewritten.
ACRONYM = re.compile(r"\bS\.?\s?M\.?\s?O\.?\s?M\b")
# Section bases of build spec section 2 (news, press, press list, galleries) whose archive is imported later.
ARCHIVE_BASES = (
    "/news/", "/it/notizie/", "/fr/actualites/", "/de/nachrichten/", "/es/noticias/",
    "/press-releases/", "/it/comunicati-stampa/", "/fr/communiques-de-presse/", "/de/pressemitteilungen/", "/es/comunicados-de-prensa/",
    "/press-publications/press-releases/", "/it/media-e-pubblicazioni/comunicati-stampa/", "/fr/press-et-publications/communiques-de-presse/",
    "/de/presse-und-veroeffentlichungen/pressemitteilungen/", "/es/prensa-y-publicaciones/comunicados-de-prensa/",
    "/photo-and-video-galleries/", "/it/gallerie-foto-e-video/", "/fr/galeries-photo-et-video/", "/de/foto-und-videogalerien/", "/es/galerias-de-fotos-y-videos/",
)
# Our own interface pages: any acronym match fails, not only one in header, nav or footer.
INTERFACE = re.compile(r"^/(?:(?:it|fr|de|es)/)?(editor|search|gdpr)/")
CHROME_TAGS = {"header", "nav", "footer"}
LOAD_TAGS = {"script", "img", "source", "video", "audio", "embed", "object", "track"}
RESOURCE_RELS = {"stylesheet", "preload", "modulepreload", "icon", "apple-touch-icon", "prefetch", "preconnect", "dns-prefetch"}
JSON_SCRIPT_TYPES = {"application/json", "application/ld+json"}
FORBIDDEN_TEXT = ("googletagmanager", "addcal", "wp-content", "cdn-cgi")


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []  # (value, role): role is "load" (fetches a resource), "hreflang" or "nav"
        self.problems = []  # inline handlers, inline scripts, iframes
        self.h1, self.title, self.desc, self.lang, self.refresh = 0, "", None, None, False
        self.main_text, self.chrome_text = [], []
        self._in_title = self._raw = False
        self._chrome = 0

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        for k in a:
            if k.startswith("on"):
                self.problems.append(f"inline event handler {k} on <{tag}>")
        if tag in CHROME_TAGS:
            self._chrome += 1
        if tag == "html":
            self.lang = a.get("lang")
        elif tag == "h1":
            self.h1 += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            if a.get("name") == "description":
                self.desc = a.get("content", "")
            if a.get("http-equiv", "").lower() == "refresh":
                self.refresh = True
        elif tag == "iframe":
            self.problems.append("<iframe> in built HTML")
        elif tag == "script":
            if "src" not in a and a.get("type", "").lower() not in JSON_SCRIPT_TYPES:
                self.problems.append("inline <script> (only JSON data blocks are allowed)")
            self._raw = True
        elif tag == "style":
            self._raw = True

        rels = set(a.get("rel", "").lower().split())
        for attr in ("href", "src", "data", "poster"):
            if attr not in a:
                continue
            if tag == "link":
                role = "load" if rels & RESOURCE_RELS else ("hreflang" if "hreflang" in a else "nav")
            elif tag in LOAD_TAGS:
                role = "load"
            else:
                role = "nav"
            self.refs.append((a[attr], role))
        if "srcset" in a:
            for part in a["srcset"].split(","):
                if part.strip():
                    self.refs.append((part.split()[0], "load"))

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag in ("script", "style"):
            self._raw = False
        elif tag in CHROME_TAGS and self._chrome:
            self._chrome -= 1

    def handle_data(self, data):
        if self._raw:
            return
        if self._in_title:
            self.title += data
        (self.chrome_text if self._chrome else self.main_text).append(data)


def redirect_sources():
    f = DIST / "_redirects"
    return [line.split()[0] for line in f.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")] if f.exists() else []


def resolves(path, sources):
    p = unquote(path)
    target = DIST / p.lstrip("/")
    if target.is_file() or (target / "index.html").is_file():
        return True
    return any(s == path or (s.endswith("*") and path.startswith(s[:-1])) for s in sources)


def check_page(rel, name, text, page, sources, fails, warns):
    refresh = page.refresh  # redirect stubs may lack h1 and description; if present they are checked
    if page.h1 != 1 and not (refresh and page.h1 == 0):
        fails.append(f"{rel}: {page.h1} <h1> elements")
    if not page.title.strip():
        fails.append(f"{rel}: empty <title>")
    if name != "404.html" and not refresh and not (page.desc or "").strip():
        fails.append(f"{rel}: missing meta description")

    if name != "404.html" and not refresh and not rel.startswith("/editor/"):
        m = re.match(r"^/(it|fr|de|es)/", rel)
        expected = m.group(1) if m else "en"
        if page.lang not in LANGS:
            fails.append(f"{rel}: <html lang> is {page.lang!r}, expected one of {', '.join(LANGS)}")
        elif page.lang != expected:
            fails.append(f"{rel}: <html lang> is {page.lang!r} but the path is {expected!r}")

    for problem in page.problems:
        fails.append(f"{rel}: {problem}")
    for word in FORBIDDEN_TEXT:
        scan = re.sub(r"https?://[a-z0-9.-]+/[^\s\"'<>)]*wp-content/uploads/[^\s\"'<>)]*", "", text.lower()) if word == "wp-content" else text.lower()
        if word in scan:
            fails.append(f"{rel}: reference to {word}")

    for ref, role in page.refs:
        ref = ref.strip()
        if ref.lower().startswith("javascript:"):
            fails.append(f"{rel}: javascript: URL")
            continue
        u = urlsplit(ref)
        if u.netloc or u.scheme in ("http", "https"):
            if u.netloc.lower() not in OWN_HOSTS:
                if role == "load":
                    fails.append(f"{rel}: loads {ref} from another origin")
                continue  # plain links to other sites are fine
            path = u.path or "/"
        else:
            if u.scheme or not u.path:
                continue  # mailto, tel, data, fragment, query only
            path = u.path
        if not path.startswith("/"):
            path = posixpath.normpath(posixpath.join(posixpath.dirname(rel), path)) + ("/" if path.endswith("/") else "")
        if not resolves(path, sources):
            if path.startswith("/wp-content/uploads/") and role != "hreflang":
                warns.append(f"{rel}: legacy upload on the live site {ref} (import with --since 2015-01-01 before launch)")
            elif role == "hreflang":
                fails.append(f"{rel}: hreflang target {ref} does not resolve")
            elif unquote(path).startswith(ARCHIVE_BASES):
                warns.append(f"{rel}: broken link {ref} (archive not yet imported)")
            else:
                fails.append(f"{rel}: broken link {ref}")
        if path.startswith("/img/") and not BRAND_FILES.match(path):
            fails.append(f"{rel}: unapproved brand asset {path}")

    chrome, main = " ".join(page.chrome_text), " ".join(page.main_text)
    if INTERFACE.match(rel) or name == "404.html":
        if ACRONYM.search(chrome + " " + main):
            fails.append(f"{rel}: forbidden acronym in our own interface text")
    elif ACRONYM.search(chrome):
        fails.append(f"{rel}: forbidden acronym in header, nav or footer")
    elif ACRONYM.search(main):
        warns.append(f"{rel}: forbidden acronym in imported text (flagged, not rewritten)")
        return 1
    return 0


def main():
    if not (DIST / "index.html").exists():
        sys.exit(f"{DIST} has no index.html: nothing to check; run python3 build.py --offline first")

    importer = ROOT / "tools" / "import_oom.py"
    if importer.exists():
        import import_oom
        self_test = getattr(import_oom, "_self_test", None)
        if self_test:
            self_test()
    else:
        print("note: tools/import_oom.py not found, importer self-test skipped")

    sources, fails, warns, pages, acronym_pages = redirect_sources(), [], [], 0, 0
    for f in sorted(DIST.rglob("*.html")):
        rel = "/" + f.relative_to(DIST).as_posix()
        text = f.read_text(encoding="utf-8")
        page = Page()
        page.feed(text)
        page.close()
        pages += 1
        acronym_pages += check_page(rel, f.name, text, page, sources, fails, warns)

    for h in HOME_PAGES:
        if not (DIST / h).is_file():
            fails.append(f"/{h}: home page missing")
    for lang in LANGS:
        f = DIST / "search" / f"index.{lang}.json"
        if not f.is_file():
            fails.append(f"/search/index.{lang}.json: search index missing")
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except ValueError as e:
            fails.append(f"/search/index.{lang}.json: not valid JSON ({e})")
            continue
        if not isinstance(data, list):
            fails.append(f"/search/index.{lang}.json: not a JSON list")

    for e in fails:
        print("FAIL", e)
    for w in warns:
        print("WARN", w)
    archive = sum(1 for w in warns if "archive not yet imported" in w)
    print(f"checked {pages} pages: {len(fails)} failures, {len(warns)} warnings "
          f"({archive} links into archive sections not yet imported, {acronym_pages} imported pages with the forbidden acronym)")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
