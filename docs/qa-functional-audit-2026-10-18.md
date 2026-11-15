# Functional QA audit

Date: 18 October 2026. Scope: every route, link, interaction and runtime behaviour of the site, before presentation to the client. Visual design was out of scope and was not changed.

Builds tested:
- the working tree at commit `6949ee0` (identical to the deployed production `maltezskyrad.vercel.app`), then the fixed branch `claude/confident-gauss-k1u2m9` (`6e13ad2`, `104546f`);
- local preview served by `python3 build.py serve` (headers and redirects applied), and the deployed Vercel production.

Tooling: `check.py`; a Python crawler over every built page (internal links, `#fragment` targets, assets, 518 distinct external `href`s); `curl` against Vercel for headers, redirects and status codes; Playwright 1.56 with Chromium 141 for all browser tests. There is no TypeScript, linter or unit-test suite in this repository; `check.py` and the CI workflow are the automated checks it has.

## Result: PASS for the fixed branch, with the conditions in "Remaining issues"

The deployed production build at `6949ee0` has no critical defect. It has eight functional defects, all fixed on the branch and all verified in Chromium on the local build. Nothing is marked verified from source inspection alone.

## Issues found and fixed

| # | Where | Defect | Fix | Verified by |
|---|---|---|---|---|
| 1 | `vercel.json` | Legacy URLs `/archiv-koncertu/…/` returned 404 on Vercel: the `:path*` pattern does not match the trailing slash that every WordPress URL carries. One current page links to such a URL. | Rule rewritten as `/archiv-koncertu/(.*)` → `$1`, the form the `/category/` rule already uses and which works on Vercel with trailing slashes. `build.py` translates `$1` for `_redirects`. | Local server 301; Vercel: see "Remaining issues" (preview is SSO-protected). |
| 2 | Grand Masters page | Link to Fra' Giacomo Dalla Torre was relative and resolved to a 404 (locally and on Vercel). | Root-relative link. `check.py` now resolves relative links, so this class fails CI; proven to flag the defect on the old build. | Crawler, Playwright, `check.py`. |
| 3 | Main menu, desktop keyboard | Escape did not close a submenu opened by keyboard focus: `:focus-within` kept it open while the item retained focus. | `site.js` marks the item `closed` on Escape until focus leaves it (or the pointer returns); one CSS rule, desktop only. Touch toggle clears it. | Playwright keyboard test, desktop and mobile. |
| 4 | Calendar block, no JavaScript | The widget showed a permanent loading state and the public-calendar link stayed hidden. | CSS: without the `js` class the block shows the fallback link instead of the loading state. | Playwright with JavaScript disabled. |
| 5 | Names of the Order (cs, en, fr, it, de) | Lead image hot-linked from orderofmalta.int: blocked by the CSP and the remote server answers 500, so the page showed a broken figure. The `og:image` was `https://www.maltezskyrad.czhttps://…`. | Image removed from the page; `build.py` no longer prefixes absolute `og:image` URLs. | Full-site Chromium sweep, meta inspection. |
| 6 | News 12 June 2023 | Five photographs hot-linked from maltezskapomoc.cz, blocked by the CSP: broken images in the article. The privacy notice says images load from this site. | Copied to `static/media/2023/06/`, article rewritten. | Full-site Chromium sweep: 7 of 7 images load. |
| 7 | `build.py serve` | The local preview server returned 404 for percent-encoded media names with diacritics (3 files), although the files exist and Vercel serves them. | Paths are unquoted before the file check. | `curl`, crawler (651/651 internal URLs 200). |
| 8 | `check.py` | Relative links were skipped, which let defect 2 through CI. | See 2. | `check.py` fails on the old build, passes on the new. |

## Tests performed and results

**Build and automated checks**
- `python3 build.py --production --offline`: 44 pages, 193 news posts, 4 × 34 translations, 398 HTML files. Succeeds.
- `python3 check.py`: 398 pages, 0 problems (one `<h1>`, title, description, internal links, brand assets, acronym, sanitiser self-test).
- GitHub Actions `build` workflow on the pushed branch: success.

**Navigation and routing**
- Crawler: 398 pages, 651 distinct internal URLs (pages, media, PDFs, fonts, CSS, JS, favicons), all 200 locally after the fixes; on Vercel production all 200 except the legacy concert-archive URL (defect 1). All `#fragment` targets exist.
- Vercel production: all 13 redirect rules exercised with `curl`; 12 work (308 to the right target), the concert-archive one did not (defect 1). Trailing-slash normalisation, `/index.html`, query strings, nested unknown paths (404) and `/nonexistent` (308 then 404) behave correctly.
- 404: unknown URLs return HTTP 404 with the Czech "Stránka nenalezena" page; its links work.
- Playwright: 29 representative pages × desktop 1440 and iPhone 13 emulation: status 200, one `<h1>`, title, no broken images, no horizontal overflow, no console errors, no failed requests.
- Full-site Chromium sweep: all 398 pages loaded and scrolled; 0 pages with console errors, failed requests, 4xx/5xx, broken images or overflow.
- Menu: hover opens exactly one dropdown and switches between items; dropdown links navigate; keyboard focus opens, Escape closes and returns focus; every menu, footer, breadcrumb and language link resolves.
- Mobile: menu starts closed, toggle opens it with `aria-expanded`, six rapid taps leave a consistent state, submenu toggles open and close, Escape closes, links inside navigate, the menu is closed again after a reload. Without JavaScript the menu and submenus are visible and usable.
- Browser back and forward across three pages; refresh during an open menu; direct URL access to every page (that is what the crawler and sweep do).
- Side-menu scroll keeping (`head.js`): clicking a side-menu link keeps the scroll position; an ordinary link starts at the top; `/#kalendar` lands on the section.
- Speculation rules: the file parses with the right content type; hovering the Kalendář link makes no AddCal request; after the click the pre-rendered page's calendar loads.

**Interactive elements and data handling**
- There are no forms, inputs, search, modals, carousels, iframes, video or cookie banner on the site (verified in the built HTML), so form validation and submission tests do not apply. No cookies are set by the site (verified after visiting several pages).
- Language switch: keeps the page where a translation exists (`/rad-a-jeho-instituce/o-radu/` → `/en/order/about/` → `/de/orden/ueber-den-orden/` → back to Czech), falls back to the language home otherwise, sets `html lang` and `aria-current`.
- News: category tabs filter and mark the current tab; the tab counter equals the number of items listed; year filter shows only that year; article pager newer/older and category links navigate correctly.
- Downloads: all 6 calendar PDFs return 200, `application/pdf`, with a `%PDF` header; 3 media PDFs linked from pages confirmed too.
- Contact: `mailto:`, two `tel:+420…` links, OpenStreetMap link; social links are https with `rel="noopener"`.
- Calendar (AddCal, the one external integration): loads lazily when near the viewport (not on hover pre-render); 108 event elements render; the public feed API answers 200; month navigation works; the Czech and English pages show localised chrome. Verified locally and on Vercel production. No CSP violations.
- Calendar failure modes: vendor blocked → `data-state="failed"` within the 15 s budget and the fallback link is shown, no page errors; vendor delayed 4 s → loading state, then ready; no JavaScript → fallback link (defect 4).

**Technical and runtime**
- Vercel production headers verified: CSP, HSTS, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, COOP, `X-Frame-Options`, `Speculation-Rules`; immutable caching on `/css/`, `/js/`, `/fonts/`; `speculation-rules.json` served as `application/speculationrules+json`; `robots.txt` allows indexing and names the sitemap; `sitemap.xml` (381 URLs) and `feed.xml` (30 items) parse.
- Console: the only messages in any run were the local-HTTP COOP notice and, once, a transient "Error loading timezones: Failed to fetch" logged by the AddCal script when two Chromium jobs shared the sandbox's proxy; the widget rendered in every other run, including on Vercel.
- Slow network: 700 ms latency on every asset, page usable, no image stuck in the loading state. Offline after load: navigation fails as expected, recovery works.
- Rendering is fully static; there is no API of the site's own, no authentication and no environment variables.

**External links** (518 distinct `href`s; 398 of them are canonical/hreflang self-references to `www.maltezskyrad.cz`)
- 120 third-party URLs checked. OK or bot-blocked (Facebook 400, YouTube 204): all but the list below.

## Remaining issues and limitations

Not fixed (content or third-party, outside a functional code fix):
- Dead external links in archived news posts and two reference pages, left as editorial decisions: `apha.cz` (2 posts from 2020), `inegal.cz` (2024 post), `malteser-international.org` (2018 posts and the humanitarian-activities page), `malteser.de/krankenhaeuser/standorte.html` (medical-activities page), `maltezskapomoc.cz/olomouc/olomouc-kontakty/` (2023 post), `orderofmalta.int/2018/05/02/…` (2018 post).
- `cmm.maltezskyrad.cz` and `gdpr.maltezskyrad.cz` (linked from three posts) serve a certificate for `maltezskyrad.cz` only; `www.zsmr.eu` (school pages) sends an incomplete certificate chain. These are the client's and the school's servers, not this site; already noted in `docs/security-audit.md`.
- The canonical host `www.maltezskyrad.cz` still redirects to the old `cvp.` host with a certificate mismatch, so the launch steps in `docs/deployment.md` remain to be done.

Not verified (blocked):
- Defect 1 on Vercel infrastructure: the branch preview deployment is behind Vercel SSO and the connected Vercel account has no scope on this project's team, so the fixed redirect could only be verified on the local server and by analogy with the identical `/category/(.*)` rule that works on Vercel. Verify after the next production deployment with `curl -I https://…/archiv-koncertu/koncert-7-prosince-2020-z-chramu-panny-marie-pod-retezem/` (expect 308).
- Vercel build logs (same scope limitation); the production build itself was reproduced locally with the exact Vercel build command.
- Firefox, Safari/WebKit and Edge: only Chromium is installed in this environment and the sandbox forbids downloading other engines. Edge shares Chromium's engine. The site uses no engine-specific API apart from progressive enhancements (view transitions, speculation rules) that degrade to plain navigation; a short smoke run in Firefox and Safari is still recommended before launch.
- Real devices and screen readers (as in the earlier QA report).

Conditions for the PASS: deploy the branch, confirm the concert-archive redirect on the live host, and run the Firefox/Safari smoke test.

## Pages and features covered

Pages (by Playwright, both viewports): `/`, `/en/`, `/fr/`, `/it/`, `/de/`, `/kalendar/`, `/en/calendar/`, `/de/kalender/`, `/aktuality/`, `/aktuality/kultura/`, `/aktuality/2024/`, two articles (2026, 2019), `/kontakt/`, `/en/contact/`, `/rad-a-jeho-instituce/`, `/rad-a-jeho-instituce/o-radu/`, `/rad-a-jeho-instituce/historie-radu-ve-svete/`, `/rad-a-jeho-instituce/velmistri/`, `/velmistr-giacoma-dalla-torre-del-tempio-di-sanguinetto/`, `/koncerty/`, `/koncerty/archiv-koncertu/`, `/radovy-kostel-panny-marie-pod-retezem/bohosluzby/`, `/cinnosti-maltezskeho-radu-v-ceske-republice/`, `/ochrana-osobnich-udaju/`, `/en/privacy/`, `/ostatni/odkazy/`, `/diplomaticke-vztahy/`, `/404.html`. All other pages: full-site sweep (398) and crawler.

Features: main menu (hover, keyboard, touch, no-JS), language switch, breadcrumbs, side menu with kept scroll, section index lists, news tabs and years, article pager, calendar widget and its failure states, calendar PDFs, contact card, footer links, 404 page, legacy redirects, security headers, RSS, sitemap, robots, speculation rules.
