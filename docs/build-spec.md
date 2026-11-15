# Build spec: orderofmalta.int on the maltezskyrad template

Contract between the work packages. If something here is wrong or impossible, make the smallest deviation and report it; do not silently diverge.

- New repo: `/home/user/orderofmalta` (GitHub `Omegaswitch/orderofmalta`). Template (read-only): `/home/user/maltezskyrad`.
- Same template, design system, security model and functions as the Czech Grand Priory site. Static HTML built by `build.py` (Python standard library + Pillow), serverless functions in `api/` (Node), hosted on Vercel.
- Rules for everyone: no git commit/push; stay inside your package's files; Python stdlib + Pillow for build/tools, Node only in `api/`, `scripts/`, `tests/`; never invent facts; never redraw or recolour an emblem; only official brand files; the four-letter acronym of the Order's name is never written by us (interface strings, docs, code comments, commit text); strict CSP, no inline scripts or event handlers, sanitised editor input, authentication on every write endpoint.

## 0. What the live site is (scouted 15 Nov 2026)

WordPress, theme `CavalieriMalta`, WPML 5.3 (en default without prefix; `/it/ /fr/ /de/ /es/`), ACF, Yoast, Max Mega Menu, Popup Maker, Relevanssi search, Google Tag Manager, Cloudflare (e-mail obfuscation).

| Thing | How to read it |
|---|---|
| Pages | REST `/wp-json/wp/v2/pages?lang=<l>&per_page=100` (en 74, it 71, …; `acf` is empty, so the body must be scraped from the page HTML: `<main id="main">` … `</main>`). `page-sitemap.xml` lists 358 URLs in all languages (one stray Cyrillic URL: skip it). |
| News | Post type `news`, REST base **`notizie`**: `/wp-json/wp/v2/notizie?lang=<l>&after=<ISO>&per_page=100`. Fields: `id, date, modified, slug, link, title.rendered, acf{news_content, news_excerpt, sub_title, news_cover{id,url}, cover_image_copyrighted, news_gallery, news_gallery_elements[{id,url}], news_video (oEmbed iframe HTML or null), breaking, evidence, focus_on, highlighted, hidden_news, not_a_news}, news_categories[{id,name,slug,link}]`. en total 2257, since 2025-01-01: 262 (it 259…). Bodies are plain (`p, strong, em, a, u, br, span, sup`), no iframes. |
| Press releases | Post type `press_releases`, **not in REST**. Listing page `/press-publications/press-releases/` (9 cards per page, `/page/N/`, 31 pages in en) gives URL, title, organisation, language, date `dd/mm/yyyy`, excerpt. Single: `<h1>`, `.box-content-meta` (Date, Organism, Language), then the text. JSON-LD has `datePublished`. |
| Galleries | Post type `galleries`, **not in REST**. Listing `/photo-and-video-galleries/` (9 per page, 27 pages in en) with date. Types (taxonomy `gallery-type`): single picture, gallery (album), video. Single: `<h1>`, `.box-content-single-gallery` (carousel of `<img>`) or `.box-content-single-gallery-video .embed-container iframe` (YouTube), `.box-content-single-data` (date + text). |
| Translations | No hreflang and no REST field. The only link between translations is the **language switcher in the page header** (`<a href="…">Italiano</a>` etc. in `.top-header`). A language without a translation is absent or points at that language's home. |
| Menus | `/wp-json/wp/v2/menus` is 401. Scrape per language home page: main mega menu `ul#mega-menu-main-menu`, footer `section.footer-links`, top bar social links. Some menu links are old aliases that 301 (e.g. `/sovereign-order-of-malta/mission/` → `/about-the-order-of-malta/mission/`). |
| Sitemaps | `/sitemap_index.xml` (no `lastmod` anywhere, so dates come from listings/REST). |
| E-mail addresses | Cloudflare-obfuscated: `<a href="/cdn-cgi/l/email-protection#HEX">` and `<span class="__cf_email__" data-cfemail="HEX">`. Decode: first byte is the XOR key for the rest. |
| Special page templates | `page-contacts` (4 region tabs × country accordions, 135 entries), `page-the-grand-masters` (timeline + tables), `page-press-and-publications` (hub), `page-publications` (cards with PDF files, 13 pages, 2 categories under `/publications-reports-categories/…`), `page-in-the-news` (external press cuttings, 108 pages), `app-landing` (`/app/`), FAQ (Bootstrap accordion), `page-home`. `/government/stamps-coins/` 301s to `https://postemagistrali.orderofmalta.int`; `/press-publications/newsletter/` 301s to `/press-publications/`. |
| Body blocks on default pages | `.box-content-title`, `.box-content-text-only-one-col|two-cols`, `.box-content-image-full-width-a`, `.box-content-mixed-one-col`, `.box-content-linked-page-one-col|two-cols` (teaser cards to other pages), `.sidebar-box` (related-page teasers, "All news"), `.box-content-photo-video-gallery-footer` (site-wide gallery carousel: drop), `.box-content-data-map`, `.accordion`. |
| Home | Carousel of the 5 latest news; "Humanitarian & medical works" list (5 links with icon + photo); "Latest News" cards; "Special organisations" (4 cards); activities map image + link to contacts; galleries carousel; three feature cards (Grand Master, Seats, Library and Archives); small boxes (contacts by continent, philately, app). A Popup Maker pop-up advertises the app. |
| Search | `/?s=term` (and `/<lang>/?s=term`), Relevanssi, server-side. |
| Feeds | `/news/feed/?lang=en`, `/it/notizie/feed/` … (RSS). |
| Year archive | `/2026/?post_type=news`, `/it/2026/?post_type=news`, paginated `/2026/page/2/?post_type=news`. |
| Embeds found | YouTube only (video galleries, one `news_video`). No Vimeo, Flickr or Issuu in the 2025+ content; support YouTube and Vimeo, turn anything else into a plain link and report it. |
| Third parties to drop | Google Tag Manager, Popup Maker, Cloudflare e-mail script, jQuery/Bootstrap/Owl/Fancybox. |

## 1. Feature inventory

| orderofmalta.int feature | In the new site | Package |
|---|---|---|
| Pages in 5 languages | Kept: every page, original URL, body normalised to the vocabulary in §3.5 | importer, build |
| Mega menu, footer menu, top-bar social links | Kept: `content/menus.json` → template main nav with grouped submenus, footer nav | importer, build, frontend |
| Language switcher | Kept: template `.lang` nav; links to the real translation, `hreflang` + `x-default` (en) in `<head>`, in the sitemap too | build |
| News: listing, categories, year archive, pagination, article with subtitle, cover, gallery, categories | Kept | importer, build |
| News tags (`breaking`, `evidence`) | Dropped: their archive pages are empty on the live site. URLs redirect to the news listing | backend (redirect) |
| Press releases (listing + single) | Kept | importer, build |
| Photo and video galleries (listing, type filter, single) | Kept, with an accessible lightbox instead of Owl/Fancybox | importer, build, frontend |
| Publications (PDF cards), "In the news" (cuttings), press hub | Kept as collections (`content/collections/`) rendered with pagination | importer, build |
| Contacts (regions, countries) | Kept: one page, regions as sections, countries as `<details>` | importer, build, frontend |
| Grand Masters timeline, FAQ accordion | Kept (`.timeline`, `<details class="acc">`) | importer, frontend |
| App landing page `/app/` | Kept as a normal page with store links (text links; store badges are third-party artwork and are not copied) | importer, build |
| App pop-up | Dropped (intrusive; the home page keeps the app box) | – |
| Search | Kept, client-side: per-language JSON index + `/search/`; `/?s=` redirects there | build, frontend, backend |
| RSS | Kept: one feed per language; old feed URLs redirect | build, backend |
| YouTube embeds | Kept, privacy-friendly: nothing loads from a third party until the visitor clicks; `youtube-nocookie.com`; optional "always" consent in `localStorage` | build, frontend, backend (CSP) |
| Skeleton / loading states | Kept from the template (`.skeleton`, `.ph-img.is-loading`), extended to search results, embeds and the lightbox | frontend |
| Staff sign-in + publishing | New for this site (the live site uses wp-admin): Better Auth (e-mail + password, Postgres, roles owner/admin/editor, no self sign-up) and the template's editor with drafts, scheduling, pinning; extended to 5 languages, translation linking, press releases and galleries | backend |
| GDPR form | Kept from the template as a single data-protection request form at `/gdpr/` (and `/<lang>/gdpr/`), e-mailed through Resend, nothing stored | build, backend |
| Security headers (CSP, HSTS, nosniff, Referrer-Policy, Permissions-Policy, COOP, X-Frame-Options) | Kept; CSP updated (AddCal out, YouTube/Vimeo frames in) | backend |
| Daily rebuild cron | Kept (`/api/rebuild`, 03:00 UTC) | backend |
| Sitemap, robots, canonical, Open Graph, JSON-LD Organization | Kept | build |
| Newsletter page | Dropped (already a redirect on the live site) → redirect to the press hub | backend |
| Stamps & coins | External site: the page is a redirect to `https://postemagistrali.orderofmalta.int/`; menus link there directly | importer, build |
| Google Tag Manager / analytics, cookie banner | Dropped: the new site sets no tracking cookies, so no banner is needed. The imported cookie-policy pages get `"status": "approval"` because their text describes the old site | importer, docs |
| AddCal calendar, church services, concerts, Grand Magistry feed, events, 2027 calendar files (template features) | Dropped: not on orderofmalta.int. Remove the code, `content/calendar.json`, the related i18n keys | build, frontend |

## 2. Languages and URLs

Languages, in this order everywhere: `en` (default, no prefix), `it`, `fr`, `de`, `es`. Site time zone: `Europe/Rome`. `baseUrl`: `https://www.orderofmalta.int`.

**Every original path is kept exactly**, for every language, with a trailing slash. Section bases (constants; build puts them in `content/site.json → sections`, the importer and the API hard-code the same table):

| key | en | it | fr | de | es |
|---|---|---|---|---|---|
| `home` | `/` | `/it/` | `/fr/` | `/de/` | `/es/` |
| `news` | `/news/` | `/it/notizie/` | `/fr/actualites/` | `/de/nachrichten/` | `/es/noticias/` |
| `press` (singles) | `/press-releases/` | `/it/comunicati-stampa/` | `/fr/communiques-de-presse/` | `/de/pressemitteilungen/` | `/es/comunicados-de-prensa/` |
| `pressList` (a page) | `/press-publications/press-releases/` | `/it/media-e-pubblicazioni/comunicati-stampa/` | `/fr/press-et-publications/communiques-de-presse/` | `/de/presse-und-veroeffentlichungen/pressemitteilungen/` | `/es/prensa-y-publicaciones/comunicados-de-prensa/` |
| `galleries` | `/photo-and-video-galleries/` | `/it/gallerie-foto-e-video/` | `/fr/galeries-photo-et-video/` | `/de/foto-und-videogalerien/` | `/es/galerias-de-fotos-y-videos/` |
| `newsCategories` | `/news-categories/` | `/it/categorie-notizia/` | `/fr/categories-de-actualites/` | `/de/nachrichten-kategorien/` | `/es/categorias-de-noticias/` |
| `newsTags` (dropped) | `/news-tags/` | `/it/tag-notizia/` | `/fr/etiquettes-de-actualite/` | `/de/nachrichten-tag/` | `/es/etiquetas-de-las-noticias/` |
| `galleryTypes` | `/gallery-type/` | `/it/tipi-di-galleria/` | `/fr/types-de-galeries/` | `/de/galerie-typen/` | `/es/tipos-de-galerias/` |
| gallery type slugs `photo, album, video` | `single-picture, gallery, video` | `singola-foto, gallery-it, video-it` | `image-unique, gallery-fr, video-fr` | `einzelnes-bild, gallery-de, video-de` | `imagen-unica, gallery-es, video-es` |
| `search` (new) | `/search/` | `/it/search/` | `/fr/search/` | `/de/search/` | `/es/search/` |
| `gdpr` (new) | `/gdpr/` | `/it/gdpr/` | `/fr/gdpr/` | `/de/gdpr/` | `/es/gdpr/` |
| `feed` (new) | `/feed.xml` | `/it/feed.xml` | `/fr/feed.xml` | `/de/feed.xml` | `/es/feed.xml` |

Derived URLs (build):

- Single items: `<news>/<slug>/`, `<press>/<slug>/`, `<galleries>/<slug>/` (as on the live site).
- Listings: 12 items per page; page 1 at the base, further pages at `<base>page/<N>/` (live scheme). Applies to news, each news category, each news year, press list, galleries, each gallery type, publications, in-the-news.
- News category: the live canonical URL of the term in that language, stored in `content/translations/categories.json` (e.g. `/news-categories/all-news/diplomatic-activities/`).
- News year archive (moved): `<news><YYYY>/`, e.g. `/news/2026/`, `/it/notizie/2026/`. (No news slug is a bare year; build fails if one is.)
- Staff editor: `/editor/` (English only, `noindex`, not linked, not in the sitemap). Its post list: `/editor/posts.json`.
- Search index: `/search/index.<lang>.json`.

Redirects (301):

| From | To | Where |
|---|---|---|
| `/?s=<q>`, `/<lang>/?s=<q>` | `<search>?q=<q>` | `vercel.json` (`has` query `s`); `site.js` does the same on other hosts |
| `/<YYYY>/?post_type=news`, `/<lang>/<YYYY>/?post_type=news`, and their `/page/N/` forms | `<news><YYYY>/` | `vercel.json` (`has` query `post_type=news`) |
| `<news>feed/`, `/feed/`, `/<lang>/feed/` | `<feed>` | `vercel.json` |
| `<press>` (bare base) | `<pressList>` | `vercel.json` |
| `<newsTags>:path*` | `<news>` | `vercel.json` |
| `/wp-admin/:path*`, `/wp-login.php`, `/wp-json/:path*`, `/xmlrpc.php` | not redirected: 404 | – |
| `/wp-content/uploads/:path*` | not redirected by pattern (file names change to `.webp`); the importer records each imported file in `content/redirects.json` only for **PDFs and other documents** (`/wp-content/uploads/2026/06/x.pdf` → `/media/2026/06/x.pdf`) | importer → build |
| Old aliases found while importing (menu links that 301, parent-less category URLs such as `/news-categories/diplomatic-activities/`, duplicate terms such as `…-2/`, `/press-publications/newsletter/` → press hub, `/en/contact/` → `/contacts/`) | their live target | importer writes `content/redirects.json`; build emits them |

`content/redirects.json` (importer): `[{"from": "/old/path/", "to": "/new/path/ or https://…"}]`, exact paths only. Build (a) writes for each a stub page `dist<from>index.html` (`<meta http-equiv="refresh" content="0;url=…">`, `<link rel="canonical">`, `noindex`, one visible link, the normal `<h1>`/title/description so `check.py` passes) and (b) appends them to `dist/_redirects`. Pattern redirects live in `vercel.json` (backend), as in the template. At integration the main session may fold `content/redirects.json` into `vercel.json` if it is small (< 500).

**Archive (items before the import cut-off).** Only items published on or after 2025-01-01 are imported now. Decision: older single-item URLs are **not** blanket-redirected to a listing (ten thousand distinct URLs pointing at one page is a soft 404 and throws the archive away). Until the full import (`tools/import_oom.py --since 2015-01-01`) is run they answer with the localised 404 page, which says the item belongs to the archive that is still being migrated and offers the search and the section listing. **Launch gate** (docs/deployment.md): before DNS moves, either run the full archive import, or keep the old WordPress on a legacy host and add after-filesystem `rewrites` in `vercel.json` for the `news`, `press` and `galleries` bases to that host. `check.py` reports internal links into those three bases that do not resolve as warnings (count), not failures.

## 3. Content model

### 3.1 Files

| Type | Path | URL |
|---|---|---|
| Page | `content/pages/<lang>/<original path without the language prefix>/index.html` (home: `content/pages/<lang>/index.html`) | original, e.g. `/it/l-ordine-di-malta/missione/` |
| News | `content/news/<lang>/<YYYY>/<file>.html` | `<news><slug>/` |
| Press release | `content/press/<lang>/<YYYY>/<file>.html` | `<press><slug>/` |
| Gallery | `content/galleries/<lang>/<YYYY>/<file>.html` | `<galleries><slug>/` |
| Collections | `content/collections/<lang>/publications.json`, `content/collections/<lang>/in-the-news.json` | rendered on the pages with template `publications` / `in-the-news` |
| Menus | `content/menus.json` | – |
| Category terms | `content/translations/categories.json` | – |
| Redirects found | `content/redirects.json` | – |
| Media | `static/media/<YYYY>/<MM>/<name>.webp` (+ `<name>-480.webp`), documents as they are | `/media/…` |
| Import state | `content/media-map.json` (source URL → `{path, w, h}`; lets re-runs and all five languages share one copy), HTTP cache in `.cache/oom/` (git-ignored) | – |

`<file>` = the slug, lower-cased, percent-decoded, every character outside `[a-z0-9-]` replaced by `-`, at most 120 characters; `<YYYY>` = year of `date`. The `url` in the front matter is authoritative (it keeps the live slug byte for byte).

Every file: JSON front matter between two `---` lines, then HTML (same reader as the template: `text.split("---\n", 2)`; the JSON must not contain a line that is exactly `---`). Written with `json.dumps(meta, ensure_ascii=False, indent=1)`.

### 3.2 Front matter (exact keys)

Common to all four types:

| Key | Type | Notes |
|---|---|---|
| `type` | `"page" \| "news" \| "press" \| "gallery"` | |
| `lang` | `"en" \| "it" \| "fr" \| "de" \| "es"` | |
| `url` | string | root-relative, trailing slash |
| `title` | string | plain text, entities decoded |
| `description` | string, optional | Yoast meta description when the page has one |
| `translations` | object `{lang: url}` | **includes the item itself**; only languages that really have a translation. This is the WPML group. Build validates symmetry and warns on a target that is not on disk |
| `id` | int, optional | WordPress post id (absent on items written in the editor) |
| `source` | string, optional | the live URL it was imported from |
| `modified` | `"YYYY-MM-DDTHH:MM"`, optional | |
| `imported` | bool | `true` when written by the importer. Anyone who edits a file by hand or through the editor sets `false`; **the importer never overwrites a file whose `imported` is `false`** |
| `status` | optional | template review states (`existing`, `new`, `approval`); shown only in preview builds |
| `image` | string or null | local `/media/…webp` (cover / hero); used for cards and `og:image` |
| `imageAlt`, `imageCredit` | string, optional | from the live `alt` / visible credit caption |

Dated types (`news`, `press`, `gallery`) add:

| Key | Type | Notes |
|---|---|---|
| `date` | `"YYYY-MM-DDTHH:MM"` | site-local (Europe/Rome), as WordPress `date` |
| `excerpt` | string | plain text, ≤ 300 characters |
| `gallery` | array of `{"src": "/media/…webp", "w": int, "h": int, "alt": "", "caption": ""}`, optional | the photo strip under a news item, or a gallery's photos |
| `video` | string, optional | canonical watch URL: `https://www.youtube.com/watch?v=<id>` or `https://vimeo.com/<id>` |
| `author`, `editedBy`, `draft`, `pinned` | as in the template | written by the editor only |

`news` only: `subtitle` (string, optional), `categories` (array of **canonical keys**, §3.3; never empty: default `["all-news"]`), `imageCopyrighted` (bool, optional).
`press` only: `organisation` (string, as shown on the live site, e.g. "SOVEREIGN ORDER OF MALTA").
`gallery` only: `kind`: `"photo" | "album" | "video"`.

`page` only:

| Key | Type | Notes |
|---|---|---|
| `parent` | url or null | the WordPress parent page's URL (same language) |
| `order` | int | `menu_order` |
| `template` | `"default" \| "home" \| "contacts" \| "timeline" \| "press-hub" \| "press-releases" \| "publications" \| "in-the-news" \| "app" \| "privacy"` | from the WordPress page template / role |
| `related` | array of local URLs, optional | the live page's sidebar teasers, in order. Build renders them as cards from the target's own `title`, `image`, `description` |
| `redirect` | string, optional | absolute URL; the page has no body (stamps & coins). Build writes a redirect stub and links menus straight to it |
| `home` | object, only on `template: "home"` | see below |

`home` object (all texts as on the live home page of that language):

```json
{"works": {"title": "humanitarian & medical works", "items": [{"title": "", "url": "", "icon": "/media/…", "image": "/media/…"}]},
 "organisations": {"title": "Special organisations", "items": [{"title": "", "url": "", "image": ""}]},
 "map": {"title": "", "image": "", "link": {"title": "", "url": ""}},
 "features": [{"heading": "Grand Master", "title": "", "text": "", "url": "", "image": ""}],
 "boxes": {"world": {"title": "", "items": [{"title": "Europe", "url": "/contacts/"}]}, "philately": {"title": "", "url": "", "image": ""}, "app": {"title": "", "text": "", "link": {"title": "", "url": "/app/"}}},
 "headings": {"latestNews": "Latest News", "galleries": "Photo & video galleries"}}
```

The news carousel, the latest-news cards and the gallery strip are filled by build from the content, not stored.

### 3.3 Categories (`content/translations/categories.json`)

Canonical key = the English term slug. News in every language store canonical keys.

```json
{"all-news": {"parent": null, "terms": {"en": {"name": "News", "slug": "all-news", "url": "/news-categories/all-news/"}, "it": {"name": "Notizie", "slug": "notizie", "url": "/it/categorie-notizia/notizie/"}}},
 "diplomatic-activities": {"parent": "all-news", "terms": {"en": {…}, "it": {…}, "fr": {…}, "de": {…}, "es": {…}}}}
```

How: REST `news_categories` on each item gives the localised term (slug, name, link); the language switcher on each English category archive page maps it to the other languages. A localised term that maps to no English term (stray duplicates such as `activites-diplomatiques-2`) is mapped by name to its obvious twin if there is exactly one with the same name in that language, else dropped from the item and reported; its URL goes to `content/redirects.json` → that language's news listing. The four filters the live listing shows first (All, Latest interventions, Grand Master, Diplomatic activities) are `site.json → newsFilters: ["latest-interventions", "grand-master-news", "diplomatic-activities"]`.

### 3.4 Menus (`content/menus.json`)

```json
{"en": {"main": [{"title": "The Order of Malta", "url": "/about-the-order-of-malta/",
                  "feature": {"title": "Mission", "url": "/about-the-order-of-malta/mission/", "image": "/media/2022/02/sovereign_mission.webp", "text": "…"},
                  "children": [{"title": "Members & Structure", "url": null, "children": [{"title": "Knights of Malta", "url": "/about-the-order-of-malta/knights-of-malta/"}]},
                               {"title": "FAQ", "url": "/about-the-order-of-malta/faq/"}]}],
        "footer": [{"title": "The Order of Malta", "url": null, "children": [ … same node shape, at most 2 levels … ]}],
        "social": [{"label": "Facebook", "url": "https://www.facebook.com/OrderOfMalta"}],
        "legal": [{"title": "Privacy Policy", "url": "/privacy-policy/"}, {"title": "Cookie Policy", "url": "/cookie-policy/"}]},
 "it": { … }}
```

Rules: URLs are local and final (aliases resolved by following the live redirect; the alias goes to `content/redirects.json`); external URLs stay absolute; links to `/wp-content/uploads/…pdf` become `/media/…pdf`; `url: null` is a heading; the dynamic "latest news" teaser inside the News mega menu is not stored; the RSS icon is not a social link. `social` is read from the desktop top bar.

### 3.5 Body HTML vocabulary

The importer turns the theme markup into this vocabulary; build and frontend render and style only this. Nothing else may appear in a body (no `style`, no `class` other than the ones listed, no `id` except heading anchors, no `script`, `iframe`, `form`, inline event handlers, `data-*`, Bootstrap classes, empty wrappers).

| Element | Use |
|---|---|
| `p, h2, h3, h4, ul, ol, li, blockquote, a, strong, em, u, s, sup, sub, br, hr, table/thead/tbody/tr/th/td` | text. Page title is the front matter `title`; the body never contains `h1`. A body's first heading that repeats the title is removed |
| `<figure class="media"><img src="/media/…webp" alt="…" width="W" height="H"><figcaption>…</figcaption></figure>` | an image in the text (`figcaption` optional). `<figure class="media media--left">` / `media--right` when the live block floats the image beside the text (`box-content-mixed-one-col`) |
| `<p class="lead">…</p>` | the highlighted first statement of a block (`box-content-container-text` first line / `small-heading`) |
| `<p class="embed"><a href="https://www.youtube.com/watch?v=ID">Title of the video</a></p>` | a video. Build expands it (§5.3). Hosts allowed: `www.youtube.com/watch?v=`, `youtu.be/`, `vimeo.com/<digits>` |
| `<p class="file"><a href="/media/…pdf">Label</a> (PDF)</p>` | a download (template convention) |
| `<details class="acc"><summary>Question</summary><div class="acc-body">…</div></details>` | FAQ items, country entries on the contacts page |
| `<section class="region" id="europe"><h2>Europe</h2>…details…</section>` | contacts regions (ids: `europe`, `africa`, `the-americas`, `asia-oceania`, or the live tab id without the `pills-` prefix in other languages) |
| `<ol class="timeline"><li><h3>…</h3>…</li></ol>` | Grand Masters timeline; the tables stay `<table>` |
| `<ul class="cards"><li><a href="/…"><img src="/media/…" alt="" width height><b>Title</b><span>Text</span></a></li></ul>` | teaser cards inside the main column (`box-content-linked-page-*`, home-like lists on hub pages). Sidebar teasers go to `related` instead |
| `<div class="cols"><div>…</div><div>…</div></div>` | two-column text blocks (`…-two-cols`, `…-split-cols`) |
| `<a class="btn" href="…">…</a>` | a call-to-action link (app store links, "Read all" of a hub block) |

Link rules: `https://www.orderofmalta.int/…` → root-relative; `http://`/`https://smom/…` typos → root-relative; uploads → `/media/…`; Cloudflare e-mail links → `mailto:`; external links keep their URL (build adds `rel="noopener"`); tracking parameters are not touched.

### 3.6 Media

- Source `https://www.orderofmalta.int/wp-content/uploads/<YYYY>/<MM>/<name>.<ext>` → `static/media/<YYYY>/<MM>/<name>.webp`. Size suffixes are stripped and the original is fetched (`-1600x852`, `-1024x640`, `-scaled`); if the original is missing use what the page had. Name: lower-case, `[a-z0-9._-]` only.
- Raster images: Pillow, EXIF orientation applied, all metadata dropped, sRGB, WebP `quality=76, method=6`. Long edge ≤ 1600 px for covers, hero and in-text images; ≤ 1280 px for `gallery` photos. Transparent PNGs keep alpha. Also write `<name>-480.webp` (width ≤ 480) for every image wider than 640 px: build uses it as the `srcset` small candidate and as the gallery thumbnail when it exists.
- PDFs and other documents (pdf, doc(x), xls(x), zip): copied unchanged to the same folder; skipped and reported when larger than 25 MB (the link then stays absolute to the live file and is listed in the report).
- SVG uploads: copied only if they contain no `<script`, `on…=` or external reference; else skipped and reported.
- Video posters: for every `video`, `https://i.ytimg.com/vi/<id>/hqdefault.jpg` → `static/media/embeds/youtube-<id>.webp` (Vimeo: skip). Build uses it when present, so nothing is requested from YouTube before the click.
- Never copied: theme files (`/wp-content/themes/…`), the header shield PNG, store badges, pop-up artwork. Brand marks come only from `static/img/` (§4).
- The importer prints the total size of `static/media` at the end; target ≤ 350 MB for the 2025+ scope.

### 3.7 Collections

`content/collections/<lang>/publications.json` (all of them, every language):

```json
{"url": "/press-publications/publications/", "title": "Order of Malta Publications",
 "categories": [{"key": "central-government", "title": "Central Government", "url": "/publications-reports-categories/central-government/"}],
 "items": [{"title": "", "date": "2026-07", "dateLabel": "July 2026", "image": "/media/…webp", "category": "central-government", "files": [{"label": "Deutsch", "url": "/media/2026/07/x.pdf"}]}]}
```

`content/collections/<lang>/in-the-news.json` (items dated on or after `--since`):

```json
{"url": "/press-publications/in-the-news/", "title": "In the news",
 "items": [{"title": "", "url": "https://…", "agency": "", "language": "FRANÇAIS", "date": "2026-11-07", "excerpt": ""}]}
```

Items keep the live order (newest first). `category` comes from walking each category listing; `date` is `YYYY-MM` when the live card shows only month and year. Build renders them, 12 per page, on the page whose `template` is `publications` / `in-the-news`, and a filtered listing at each category `url`. The press hub (`template: "press-hub"`) shows the latest three of each plus the latest press releases.

### 3.8 Importer command

```
python3 tools/import_oom.py [--since 2025-01-01] [--langs en,it,fr,de,es]
        [--types menus,pages,categories,news,press,galleries,collections] [--limit N] [--no-media] [--refresh] [--workers 4]
```

- Default: everything above, since 2025-01-01, all languages. `--since 2015-01-01` later imports the full archive with the same code.
- Polite: at most 4 concurrent requests, a generic User-Agent without personal details, retries with back-off, every response cached in `.cache/oom/` so re-runs do not hit the site again (`--refresh` ignores the cache).
- Re-runnable: a file whose front matter says `"imported": false` is never overwritten; other files are rewritten only when the content changed; nothing is deleted.
- Ends with a report on stdout: counts per type and language, items without a translation group, dropped category terms, skipped or oversized files, unknown embeds, pages whose body still contains unmapped markup, total media size.
- `_self_test()` (called by `check.py`): unit checks of the pure functions (slug → file name, e-mail decoding, size-suffix stripping, body normalisation samples, front matter round trip) without network.

## 4. Site identity

`content/site.json` (build) — keys: `baseUrl`, `languages` (`["en","it","fr","de","es"]`), `timezone` (`"Europe/Rome"`), `repo` (`"Omegaswitch/orderofmalta"`), `names`, `contact`, `sections` (§2 table), `galleryTypes`, `newsFilters`, `perPage` (12), `editorUrl` (`"/editor/"`). The API reads `languages`, `sections`, `timezone`, `baseUrl` from this file, so keep those names.

Names (taken from the live site's own header and footer; do not paraphrase):

| | `order` (full) | `orderShort` | `orderActivities` |
|---|---|---|---|
| en | Sovereign Military Hospitaller Order of St John of Jerusalem of Rhodes and of Malta | Sovereign Order of Malta | Order of Malta |
| it | Sovrano Militare Ordine Ospedaliero di San Giovanni di Gerusalemme di Rodi e di Malta | Sovrano Ordine di Malta | Ordine di Malta |
| fr | Ordre Souverain Militaire et Hospitalier de Saint-Jean de Jérusalem de Rhodes et de Malte | Ordre souverain de Malte | Ordre de Malte |
| de | Souveräner Ritter- und Hospitalorden vom Hl. Johannes zu Jerusalem von Rhodos und von Malta | Souveräner Malteserorden | Malteserorden |
| es | Soberana y Militar Orden Hospitalaria de San Juan de Jerusalén de Rodas y de Malta | Soberana Orden de Malta | Orden de Malta |

`names[lang].site` = `orderShort`; `names[lang].lockup` = `orderShort`. There is no `entity` (this is the Grand Magistry's own site): remove it from the layout.

Contact (live footer): Magistral Palace, Via Condotti, 68 – 00187 Rome – Italy; Tel. +39.06.67581.1; `info@orderofmalta.int`; history and bibliography: `info.biblio@orderofmalta.int`. Per-language address lines come from each language's live footer (`.footer-credits`); build copies them from the importer's `content/menus.json → <lang>.footerCredits` (`{"name": "", "address": "", "phone": "", "email": ""}`) if present, else uses the English line. No company number, no named person.

Social links (live top bar): Facebook `https://www.facebook.com/OrderOfMalta`, X `https://twitter.com/orderofmalta`, YouTube `https://www.youtube.com/c/orderofmaltaofficialchannel`, Instagram `https://www.instagram.com/orderofmalta_official/`, LinkedIn `https://it.linkedin.com/company/order-of-malta` — taken from `menus.json → social`, text labels only (no third-party logos).

`content/i18n.json` (build): the five languages, every interface string the build and the scripts need (keys in §5.6). Translate carefully; where the live site already has the wording (News, Press Releases, Read all, Search, Categories, Date, Language, Organization, Latest news, Select Year, News Archive, Photo and Video galleries, Photos, Photo Albums, Video, Contacts …) use the live wording of that language.

**Lockups.** The guidelines' lettering (Century Gothic Bold) is a licensed font that is not in the repository and not on this machine, so outlined lockups cannot be produced here. Therefore:

- `tools/make_lockup.py` (build): `NAMES` becomes one line per language, the upper-cased `orderShort` (SOVEREIGN ORDER OF MALTA, SOVRANO ORDINE DI MALTA, ORDRE SOUVERAIN DE MALTE, SOUVERÄNER MALTESERORDEN, SOBERANA ORDEN DE MALTA), no second line. With a font path it writes outlined `static/img/lockup/<lang>.svg` exactly as before. With `--shield` (no font needed, standard library only) it writes `static/img/lockup/shield.svg`: the official shield group copied **unchanged** (same paths, same colours) from the template's lockup, view box cropped to the shield. Run `--shield` now.
- Delete `static/img/lockup/{cs,en,fr,it,de}.svg` and `static/img/og-{cs,en,fr,it,de}.jpg` from the scaffold: they say "Czech Republic".
- Layout: when `static/img/lockup/<lang>.svg` exists use it as in the template; otherwise the banner link is `<a class="banner-home" href="…"><img class="lockup lockup--shield" src="/img/lockup/shield.svg" alt="" width height><span class="lockup-text">Sovereign Order of Malta</span></a>` (live text beside the official shield, which is what orderofmalta.int itself does), followed by `<p class="fullname">` with the full name.
- `tools/make_og.py` (build): 1200×630 cards `static/img/og-<lang>.jpg` for the five languages, same recipe (flag photograph under the dark veil, red strip), with the outlined lockup if it exists, else the shield plus the name set in the site's own Asap 700 (loaded from `static/fonts`). It needs Playwright (`pip install playwright`; Chromium is at `/opt/pw-browsers/chromium`); these are developer tools, not build dependencies. If it cannot run here, say so and leave no OG file that shows the Czech lockup (build then omits `og:image`).
- Record the open item in `docs/brand-compliance.md` (docs): outlined lockups need the licensed font and the Grand Magistry's approval.

Brand files allowed under `/img/` (`check.py`): `emblems/armorial-bearing-(420|840).webp`, `banner/banner-photo.webp`, `og-(en|it|fr|de|es).jpg`, `lockup/(shield|en|it|fr|de|es).svg`, `favicon/*`.

## 5. Interfaces between build, frontend and backend

Build emits the HTML; frontend styles and scripts exactly these hooks; backend's CSP must allow exactly what they need. Keep every template class that is still used (`.wrap, .page, .page-head, .display, .display-s, .lead-s, .prose, .tabs, .years, .news-list, .n-item, .side-nav, .index-list, .btn, .link-strong, .file, .photo-run, .ph-img, .skeleton, .pinned, .home-feature/.hf-*, .content-status, .topbar, .banner, .mainnav, .menu, .nav-list, .has-sub, .sub, .sub-toggle, .menu-toggle, .lang, .site-footer, .f-nav, .f-id, .f-red, .ne*, .gdpr-form, .skip, .crumbs`). New hooks:

### 5.1 Page frame

- `<html lang="…">`; `head.js` adds `.js` to `<html>` (template).
- Head: one data block, not executed, allowed by the CSP like the template's JSON-LD:
  `<script type="application/json" id="site-data">{"lang":"it","home":"/it/","search":{"url":"/it/search/","index":"/search/index.it.json"},"archiveBases":["/it/notizie/","/it/comunicati-stampa/","/it/gallerie-foto-e-video/"],"t":{…strings of §5.6 that scripts need…}}</script>`
- Top bar: `<a class="topbar-home">`, `<span class="topbar-social">`, **`<form class="site-search" role="search" action="<search>" method="get"><label class="visually-hidden" for="site-q">…</label><input id="site-q" type="search" name="q" autocomplete="off"><button type="submit" aria-label="…"></button></form>`**, `<nav class="lang" aria-label="…">` with five `<a href lang hreflang [aria-current="true"] title="Italiano">IT</a>`.
- Main nav: template structure; a submenu may contain groups and one feature card:
  `<ul class="sub"><li class="sub-feature"><a href><img class="ph-img" …><b>Mission</b><span>…</span></a></li><li class="sub-group"><span class="sub-heading">Members &amp; Structure</span><ul><li><a href>…</a></li></ul></li><li><a href>FAQ</a></li></ul>`
- Footer: `.f-nav` holds the footer menu as columns: `<div class="f-col"><h2>Title</h2><ul>…</ul></div>` (a heading without URL is a `<h3 class="f-heading">` inside the list); `.f-id` name, address, phone, e-mail; `.f-red` legal links (privacy, cookie policy, GDPR) and the app link.
- Breadcrumbs: template `crumbs_html`.
- `<main id="main" class="…" tabindex="-1">`.

### 5.2 Listings and cards

```html
<nav class="tabs" aria-label="Categories"><a href="/news/" aria-current="page">All</a><a href="…">Diplomatic Activities</a></nav>
<ol class="card-grid">            <!-- news, galleries; .card-grid--text for press and in-the-news (no image) -->
 <li class="card card--news">     <!-- card--news | card--press | card--gallery | card--publication | card--cutting | card--page -->
  <a class="card-media" href="/news/x/" tabindex="-1" aria-hidden="true"><img class="ph-img" src srcset sizes alt="" width height loading="lazy" decoding="async"></a>
  <div class="card-body">
   <p class="card-meta"><time datetime="2026-11-09">9 November 2026</time><span class="card-kind">Video</span></p>
   <h2 class="card-title"><a href="/news/x/">Title</a></h2>     <!-- h3 on the home page and in "related" -->
   <p class="card-text">Excerpt…</p>
   <ul class="card-files"><li><a href="/media/…pdf">Deutsch</a></li></ul>   <!-- publications only -->
  </div>
 </li>
</ol>
<nav class="pager" aria-label="Pages"><a class="pager-prev" rel="prev" href>…</a><ol><li><a href aria-current="page">1</a></li><li><a href>2</a></li><li class="pager-gap">…</li></ol><a class="pager-next" rel="next" href>…</a></nav>
<nav class="years" aria-label="News archive"><a href="/news/2026/">2026</a>…</nav>
```

- Article page: `<article class="article article--news|press|gallery">` with `<header class="page-head">` (`<p class="kicker">` section link, `<h1 class="display">`, `<p class="subtitle">`, `<p class="article-meta"><time>…</time> · organisation</p>`), cover `<figure class="article-cover">`, `<div class="prose">` body, categories `<ul class="tag-list"><li><a href>…</a></li></ul>`, the gallery (§5.4), `<nav class="article-nav">` previous / next in the same language and type, `<aside class="related">` (latest three news as `.card-grid`).
- Page with sidebar teasers: `<aside class="related"><h2>…</h2><ol class="card-grid card-grid--side">…card--page…</ol></aside>` after the body; the template's `.side-nav` (children/siblings from `parent`) stays.
- Home (`<main class="home">`): `.home-feature` carousel (template markup, news tab only: the "coming up" tab is removed), `<section class="home-works">` (`<ul class="works"><li><a href><img class="works-icon"><b>…</b></a></li></ul>`), `<section class="home-news">` (6 cards + link to all), `<section class="home-orgs">` (4 `card--page`), `<section class="home-map">` (image + link), `<section class="home-galleries">` (6 `card--gallery`), `<section class="home-features">` (3 cards), `<section class="home-boxes">` (`.box.box--world`, `.box.box--philately`, `.box.box--app`). Pinned notices: template `.pinned` on the home and news listing of the post's own language.

### 5.3 Embeds (click to load)

Build expands every `<p class="embed"><a href>…</a></p>` in a body and every `video` front matter value to:

```html
<figure class="embed" data-embed="youtube" data-src="https://www.youtube-nocookie.com/embed/ID?autoplay=1&rel=0" data-state="idle">
 <button class="embed-load" type="button">
  <img class="embed-poster ph-img" src="/media/embeds/youtube-ID.webp" alt="" width="480" height="360" loading="lazy" decoding="async">  <!-- only if the file exists -->
  <span class="embed-play" aria-hidden="true"></span>
  <span class="embed-title">Title of the video</span>
 </button>
 <div class="skeleton embed-skeleton" aria-hidden="true"><span></span></div>
 <figcaption><span class="embed-note">Playing the video loads it from YouTube, which may set cookies.</span>
  <label class="embed-always"><input type="checkbox"> Always load videos from YouTube</label>
  <a class="embed-link" href="https://www.youtube.com/watch?v=ID" rel="noopener">Watch on YouTube</a></figcaption>
</figure>
```

- `data-embed`: `youtube` (`data-src` on `https://www.youtube-nocookie.com/embed/`) or `vimeo` (`https://player.vimeo.com/video/<id>?autoplay=1&dnt=1`).
- Script (frontend): click → `data-state="loading"` (skeleton shown) → insert `<iframe src=data-src title allow="autoplay; encrypted-media; picture-in-picture; fullscreen" allowfullscreen loading="lazy" referrerpolicy="strict-origin-when-cross-origin">` → on `load` `data-state="ready"`. The checkbox stores `localStorage["oom-embed-consent"]` (comma list of providers); with consent an embed loads when it scrolls into view, never while `document.prerendering`. Without JavaScript the link under the poster works. No request to a third party before the click or stored consent.
- CSP (backend): `frame-src https://www.youtube-nocookie.com https://player.vimeo.com`; nothing else changes for embeds (`img-src` stays `'self' data: blob:` because posters are local).

### 5.4 Gallery and lightbox

```html
<ul class="gallery" data-lightbox>
 <li><a href="/media/2026/11/2.webp" data-w="1280" data-h="853" data-caption="…"><img class="ph-img" src="/media/2026/11/2-480.webp" alt="…" width="480" height="320" loading="lazy" decoding="async"></a></li>
</ul>
```

- Build emits it for `gallery` front matter (news: under the text with `<h2>` "Gallery"; galleries of kind `photo`/`album`: above the text) and adds `data-lightbox` to the template's `.photo-run` (photos staff insert in a text).
- Script (frontend): one native `<dialog class="lightbox">` per page, created on first use: `<figure><img><figcaption></figcaption></figure>`, buttons `.lightbox-prev`, `.lightbox-next`, `.lightbox-close`, counter `.lightbox-count` ("3 / 9"), `data-state="loading|ready"` with a `.skeleton` while the large image loads; arrow keys, Escape, swipe, focus returns to the thumbnail, body scroll locked, `prefers-reduced-motion` respected. Without JavaScript each thumbnail opens its image.

### 5.5 Search

- Index (build), one per language, `dist/search/index.<lang>.json`: `[{"u": "/news/x/", "t": "Title", "d": "2026-11-09", "k": "news|press|gallery|page", "x": "excerpt or description, then body text, ≤ 600 characters"}]`, minified, newest first, drafts and future posts excluded, only that language's items. Served with the long cache of static files but fetched with `?v=<ASSET_VERSION>`.
- Page (build), `<search>`: `<main class="search-page">`, `<h1>`, `<form class="search-form" role="search" action="" method="get"><input type="search" name="q" id="search-q"><button type="submit">Search</button></form>`, `<p class="search-status" role="status" aria-live="polite"></p>`, `<div class="search-results" data-state="idle"><div class="skeleton search-skeleton" aria-hidden="true"><span></span>×6</div><ol class="card-grid card-grid--text" id="search-list"></ol></div>`, `<noscript>` with a link to the news listing. `noindex`.
- Script (frontend, `static/js/search.js`, loaded only on the search page): reads `q`, sets `data-state` `loading → ready | empty | failed`, fetches the index named in `#site-data`, matches all words case- and accent-insensitively (`normalize("NFD")`), title hits first then date, renders at most 50 results as `card card--<k>` list items built with `textContent`/`createElement` only (never `innerHTML` with index data), keeps `?q=` in the address, `<mark>` around hits via text nodes.
- `site.js`: on any page, `?s=<q>` in the address redirects to `<search>?q=<q>` (covers hosts without the `vercel.json` rule).

### 5.6 i18n keys (`content/i18n.json`, per language)

Kept from the template: `langName, skip, menu, langLabel, home, news, contact, inSection, allNews, backToNews, category, allCategories, year, files, privacy, gdpr, notFound, notFoundText, address, phone, email, status{…}, months[12], morePages, breadcrumb, armsAlt`.
New: `search, searchLabel, searchPlaceholder, searchNone, searchCount ("{n} results"), searchLoading, searchFailed, readMore, pressReleases, galleries, galleryPhoto, galleryAlbum, galleryVideo, galleryHeading, publications, inTheNews, organisation, language, date, agency, latestNews, newsArchive, selectYear, related, previous, next, pagerLabel, page ("Page {n}"), embedNote ("Playing the video loads it from {provider}, which may set cookies."), embedAlways ("Always load videos from {provider}"), embedWatch ("Watch on {provider}"), embedPlay ("Play video: {title}"), lightboxClose, lightboxPrev, lightboxNext, lightboxOf ("{i} / {n}"), archiveNote ("This item belongs to the archive, which is still being migrated."), cookiePolicy, appLink, redirecting, gdprTitle, gdprLead, gdprName, gdprEmail, gdprType, gdprTypes{access, rectification, erasure, objection, other}, gdprMessage, gdprSend, gdprSending, gdprSent, gdprFailed, gdprTooFast, gdprNotSet`.
Removed: everything about the calendar, services, concerts, feasts, the Grand Priory, the Czech news notice.

### 5.7 Staff editor and API

- Page `/editor/` (build): `layout(lang="en", …)` around the fragment **`templates/editor.html`** (backend-owned; plain HTML, English labels, the template's `ne-*` ids and classes). Build loads `/js/vendor/quill-2.0.3/…` and `/js/news-editor.js` exactly as the template's `render_news_editor()` does, and writes `dist/editor/posts.json`: `[{"path": "content/news/en/2026/x.html", "type": "news", "lang": "en", "url", "title", "date", "author", "editedBy", "draft", "pinned", "translations": {…}}]` for all news, press releases and galleries including drafts and scheduled posts.
- `api/news.js` (backend), same actions as the template (`login` legacy only, `logout`, `upload`, `publish`, `load`, `delete`) plus fields `type` (`news|press|gallery`), `lang`, `translationOf` (the `path` of a post in another language) and `video`. It writes only: `content/news/<lang>/<YYYY>/<slug>.html`, `content/press/<lang>/<YYYY>/<slug>.html`, `content/galleries/<lang>/<YYYY>/<slug>.html`, `static/media/<YYYY>/<MM>/…`. Front matter exactly as §3.2 (`imported: false`, `author`, `editedBy`, `draft`, `pinned`, `translations` including itself). Linking a translation updates the `translations` map of every member of the group in the same commit. Slug from the title (template `slugify`, fallback `news`); URL `<base for type and lang><slug>/`.
- Sanitiser: the template allowlist plus `<p class="embed"><a href>` (only the hosts of §3.5; any other `class` is dropped) and `<p class="file">` as today.
- `GET /api/news` info adds `languages`, `types`, `categories` (canonical key → label per language, read from `content/translations/categories.json`).
- Auth: Better Auth as in the template (`api/_auth.mjs`, `api/auth.js`, rewrite `/api/auth/(.+)`), roles `owner`/`admin`/`editor`, no self sign-up, 12-hour sessions, rate limit; the legacy `NEWS_USERS` path stays only so the stubbed tests and `tests/news.local.js` run without a database.
- `api/gdpr.js`: one form id `data-request`; `GDPR_TO` and `MAIL_FROM` have **no default** (503 `config` when unset: we do not invent an address); subject and body in English; time zone Europe/Rome. Form markup (build): `<form class="ne gdpr-form" data-form="data-request">` with `data-label` on each field, hidden honeypot `_hp`, `.ne-msg`, as in the template; `static/js/gdpr.js` (frontend) reads its messages from `#site-data.t`.

## 6. Work packages (exclusive ownership)

| Package | Model | Owns |
|---|---|---|
| importer | Sonnet | `tools/import_oom.py` (deletes `tools/import_wp.py`), `content/pages/`, `content/news/`, `content/press/`, `content/galleries/`, `content/collections/`, `content/translations/`, `content/menus.json`, `content/redirects.json`, `content/media-map.json`, `static/media/` |
| build | Sonnet | `build.py`, `content/site.json`, `content/i18n.json`, `tools/make_lockup.py`, `tools/make_og.py`, `static/img/` (deletes `content/calendar.json`) |
| frontend | Sonnet | `static/css/`, `static/js/` except `static/js/vendor/` and `static/js/news-editor.js`, `static/speculation-rules.json`, `DESIGN.md` |
| backend | Sonnet | `api/`, `scripts/`, `tests/`, `templates/editor.html`, `static/js/news-editor.js`, `package.json`, `package-lock.json`, `vercel.json` |
| docs | Haiku | `README.md`, `PRODUCT.md`, `CLAUDE.md` (rules kept), `docs/*.md` except `docs/build-spec.md` |
| checks | Haiku | `check.py`, `.github/workflows/ci.yml` |

Working in parallel: `build.py` reads its content root from the environment variable `OOM_CONTENT` (default `content/`), so the build package can develop against fixtures it writes in its scratch directory in the formats of §3 while the import runs; the importer does a first small run (`--limit 5`) early so real files exist soon.

Acceptance for the whole: `python3 build.py --offline && python3 check.py` passes; `node tests/news.test.js && node tests/gdpr.test.js` pass; every live URL from the five sitemaps that is in the import scope answers 200 or a redirect in `python3 build.py serve`; no request leaves the site's origin on any page before a visitor asks for an embed.
