# Content inventory

Source: the live site www.orderofmalta.int (WordPress with WPML). Scouted on 15 Nov 2026; the details are in `docs/build-spec.md`, sections 0 to 3. Per-page and per-type counts are filled in after the import. They are not estimated here.

## Content types

| Type | Live source | Stored as | Notes |
|---|---|---|---|
| Pages | WordPress pages, in all five languages (REST `pages`, body scraped from the HTML) | `content/pages/<lang>/…/index.html` | Every page keeps its original path. Special templates: contacts, Grand Masters, press hub, publications, in the news, app, FAQ, home. |
| News | WordPress post type `news` (REST base `notizie`) | `content/news/<lang>/<YYYY>/<file>.html` | Categories as canonical keys. Optional photo gallery and video. |
| Press releases | Post type `press_releases`, not in the REST API; read from the listing and single pages | `content/press/<lang>/<YYYY>/<file>.html` | Organisation, language and date from the page. |
| Photo and video galleries | Post type `galleries`, not in the REST API; read from the listing and single pages | `content/galleries/<lang>/<YYYY>/<file>.html` | Kinds: photo, album, video. |
| Publications | Page template `publications`, cards with PDF files | `content/collections/<lang>/publications.json` | Thirteen listing pages on the live site; two categories. |
| In the news | Page template `in-the-news`, external press cuttings | `content/collections/<lang>/in-the-news.json` | Items from 1 Jan 2025 are imported. |
| Menus and footer | Scraped from each language home page | `content/menus.json` | Main mega menu, footer links, social links, legal links. |
| Media | `/wp-content/uploads/…` | `static/media/<YYYY>/<MM>/` | Images as WebP. Documents unchanged. |
| Category terms | News categories in each language | `content/translations/categories.json` | Canonical key is the English term slug. |

## URL scheme

Every original path is kept, with a trailing slash. The table is the same as `docs/build-spec.md`, section 2.

| Key | en | it | fr | de | es |
|---|---|---|---|---|---|
| Home | `/` | `/it/` | `/fr/` | `/de/` | `/es/` |
| News | `/news/` | `/it/notizie/` | `/fr/actualites/` | `/de/nachrichten/` | `/es/noticias/` |
| Press releases (single items) | `/press-releases/` | `/it/comunicati-stampa/` | `/fr/communiques-de-presse/` | `/de/pressemitteilungen/` | `/es/comunicados-de-prensa/` |
| Press list (a page) | `/press-publications/press-releases/` | `/it/media-e-pubblicazioni/comunicati-stampa/` | `/fr/press-et-publications/communiques-de-presse/` | `/de/presse-und-veroeffentlichungen/pressemitteilungen/` | `/es/prensa-y-publicaciones/comunicados-de-prensa/` |
| Galleries | `/photo-and-video-galleries/` | `/it/gallerie-foto-e-video/` | `/fr/galeries-photo-et-video/` | `/de/foto-und-videogalerien/` | `/es/galerias-de-fotos-y-videos/` |
| News categories | `/news-categories/` | `/it/categorie-notizia/` | `/fr/categories-de-actualites/` | `/de/nachrichten-kategorien/` | `/es/categorias-de-noticias/` |
| Gallery types | `/gallery-type/` | `/it/tipi-di-galleria/` | `/fr/types-de-galeries/` | `/de/galerie-typen/` | `/es/tipos-de-galerias/` |
| Gallery type slugs (photo, album, video) | `single-picture`, `gallery`, `video` | `singola-foto`, `gallery-it`, `video-it` | `image-unique`, `gallery-fr`, `video-fr` | `einzelnes-bild`, `gallery-de`, `video-de` | `imagen-unica`, `gallery-es`, `video-es` |
| Search (new) | `/search/` | `/it/search/` | `/fr/search/` | `/de/search/` | `/es/search/` |
| Data-protection request form (new) | `/gdpr/` | `/it/gdpr/` | `/fr/gdpr/` | `/de/gdpr/` | `/es/gdpr/` |
| Feed (new) | `/feed.xml` | `/it/feed.xml` | `/fr/feed.xml` | `/de/feed.xml` | `/es/feed.xml` |

Derived addresses:

- Single items: `<news>/<slug>/`, `<press>/<slug>/`, `<galleries>/<slug>/`.
- Listings show 12 items per page. Page 1 is at the base, and later pages are at `<base>page/<N>/`. This applies to news, each news category, each news year, the press list, galleries, each gallery type, publications and in the news.
- News year archive: `<news><YYYY>/`, for example `/news/2026/`. No news slug may be a bare year.
- The editor is at `/editor/` (English only, not indexed). The search index is at `/search/index.<lang>.json`.

## Import scope

- **Pages:** all pages in all five languages.
- **News, press releases, galleries, publications and in the news:** items published on or after 1 Jan 2025 (`--since 2025-01-01`).
- **Older items:** not imported yet. The full archive is imported with `--since 2015-01-01` before launch, or the old host is kept for the old addresses (the launch gate in `docs/deployment.md`). Until then, an old item's address shows the 404 page. That page says the item belongs to the archive that is still being migrated, and it offers the search and the section listing.
- **Live size on 15 Nov 2026, for scale only:** about 2,257 English news items in total, 262 of them from 1 Jan 2025. Italian: 259 from 1 Jan 2025.

Per-type and per-language counts after the import: **filled in after the import**.

## What is dropped, and why

| Live feature | Decision | Reason |
|---|---|---|
| News tags (`breaking`, `evidence`) | Dropped. Their addresses redirect to the news listing. | Their archive pages are empty on the live site. |
| App pop-up | Dropped. | Intrusive. The home page keeps the app box. |
| Newsletter page | Dropped. It redirects to the press hub. | Already a redirect on the live site. |
| Google Tag Manager and other analytics | Dropped. | The new site sets no tracking cookies. |
| Cookie banner | Not built. | No cookies need consent. |
| Popup Maker, jQuery, Bootstrap, Owl and Fancybox | Dropped. | Replaced by the template's own code. |
| Cloudflare e-mail script | Dropped. E-mail addresses are written as plain `mailto:` links. | Not needed. |
| Store badges for the app | Not copied. The app page keeps text links. | Third-party artwork. |
| The stamps and coins page | Becomes a redirect to `https://postemagistrali.orderofmalta.int/`. | The page is an external site. |
| Calendar, church services, concerts, feasts and Grand Magistry feed | Not on the site. Removed from the code and `content/`. | Template features that this site does not have. |
| Search with WordPress (Relevanssi) | Replaced by a client-side search with one index per language. | The static site has no server search. |
| `/wp-admin/`, `/wp-login.php`, `/wp-json/`, `/xmlrpc.php` | Not redirected. They answer 404. | No WordPress on the new site. |

## Redirects

| From | To | Where |
|---|---|---|
| `/?s=<q>` and `/<lang>/?s=<q>` | `<search>?q=<q>` | `vercel.json`; `site.js` does the same on other hosts |
| `/<YYYY>/?post_type=news` and `/<lang>/<YYYY>/?post_type=news`, with `/page/N/` | `<news><YYYY>/` | `vercel.json` |
| News feed, `/feed/` and `/<lang>/feed/` | The new feed | `vercel.json` |
| The bare press base | The press list | `vercel.json` |
| News tags and their sub-paths | The news listing | `vercel.json` |
| Old aliases found while importing (menu links that redirect, parent-less category addresses, duplicate terms such as `…-2/`, the newsletter page, `/en/contact/`) | Their live target | `content/redirects.json`, written by the importer. The build writes a stub page and `dist/_redirects` for each |
| Uploaded PDFs and other documents (`/wp-content/uploads/…`) | `/media/…` | `content/redirects.json`, for documents only |

Uploaded images are not redirected by pattern, because their file names change to `.webp`.

Items found in `content/redirects.json` after the import: **filled in after the import**.

## Open items

- Per-type counts, dropped category terms, skipped or oversized files and the total size of `static/media` come from the import report. They are not in this document yet.
- Whether the old host is kept, and for how long, is open (see `docs/deployment.md`).
