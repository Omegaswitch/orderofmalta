# maltezskyrad.cz

Website of the Czech Grand Priory of the Sovereign Military Hospitaller Order of St. John of Jerusalem of Rhodes and of Malta (České velkopřevorství Suverénního vojenského špitálního řádu svatého Jana Jeruzalémského, z Rhodu a z Malty).

The site is static. A Python script (standard library only) turns the files in `content/` into plain HTML in `dist/`. It has no CMS, no database and no packages to install.

## Commands

```sh
python3 build.py serve 8000      # preview build, then serve it at http://localhost:8000 (headers and redirects applied)
python3 build.py                 # preview build into dist/ (noindex, status labels shown)
python3 build.py --production    # production build (see docs/deployment.md)
python3 check.py                 # checks dist/: links, headings, descriptions, brand assets, acronyms
```

Add `--offline` to skip fetching the Grand Magistry news feed. CI (`.github/workflows/ci.yml`) runs the build and `check.py` on every push.

## Where things are

| Path | What |
|---|---|
| `content/pages/<url>/index.html` | Pages. Each file has JSON front matter between `---` lines, then HTML. |
| `content/news/YYYY/MM/DD/slug.html` | News posts. The URL matches the old WordPress URL. |
| `vercel.json` | Hosting settings, security headers (CSP, HSTS…) and legacy-URL redirects; the build copies them to `dist/_headers` and `dist/_redirects`. |
| `content/site.json` | Names, contact details, service times, menu, 2027 calendar files, AddCal calendar. |
| `content/i18n.json` | Interface strings in cs, en, fr, it and de. |
| `content/translations/<lang>.json` | Translated pages (en, fr, it, de), keyed by the Czech page URL: `url`, `title`, `description`, `body`. A page without an entry is simply not in that language's menu. |
| `content/calendar.json` | 2027 events, Order feasts, concert dates and Lent services in all five languages. |
| `static/` | CSS, JS, fonts, official brand files (`img/`), calendar PDFs (`files/`) and migrated media (`media/`). |
| `tools/import_wp.py` | One-off importer from the old WordPress site. Re-running it never overwrites a file marked `"imported": false`. |
| `tools/make_og.py` | Builds `static/img/og-<lang>.jpg`, the 1200×630 link-preview cards (Discord, iMessage, Facebook): the Order's flag under a dark veil, the lockup in that language, a red strip. Same recipe as the school sites. |

## Editorial workflow

**Monthly church notice or concert**
1. Copy last month's file in `content/news/`. Give it a new date folder and slug.
2. Edit the front matter (`title`, `url`, `date`, `categories`, `excerpt`) and the HTML below it.
3. Put the PDF in `static/media/YYYY/MM/` and link it as `<p class="file"><a href="/media/…pdf">Stáhnout</a> (PDF)</p>`.

**Changing a page**
- Edit its file. Set `"imported": false` in the front matter so a re-import never overwrites it.
- Set `"status"` to show the review state in preview builds:
  - `existing`: carried over, not yet reviewed;
  - `new`: new text awaiting approval;
  - `approval`: needs sign-off;
  - remove the field once the page is approved.

**News from co-workers (no GitHub needed)**
- Staff publish at `/pridat-aktualitu/` (not linked from the site, not indexed, behind a password). The page has a text editor limited to what the site styles: heading and subheading, bold, italic, underline, strikethrough, lists, quotes, links and photos in the text; plus date, categories, an optional summary, a main photo and downloadable attachments.
- Photos are shrunk in the browser (1600 px, WebP or JPEG, which also removes camera location data). Several photos can be inserted into the text at once; two or more in a row appear as a photo grid. Every file is sent in its own request (Vercel accepts at most 4.5 MB per request): PDF and photos up to 3 MB each, checked on the server by their content, not just the name, and saved under a new random name. PDFs over 1 MB are shrunk in the browser by Ghostscript compiled to WebAssembly (`static/js/pdf-worker.js`, `static/js/vendor/ghostscript-1.1.0/`, AGPL: licence and source links in that folder, offered on the staff page), loaded only when such a PDF is attached.
- The tab **Upravit nebo smazat** lists every post (searchable). Editing keeps the post's address and earlier fields, and records who edited it (`editedBy`). Older imported posts with captioned photos, dividers or tables keep their text unchanged; their title, date, categories, summary, photo and attachments can still be edited. Deleting removes the post in one commit (the media files stay).
- `api/news.js` cleans the text (an allowlist of tags; scripts, styles and foreign attributes are removed) and commits the article to `main` as `content/news/YYYY/MM/DD/slug.html` with its files in `static/media/YYYY/MM/`. Vercel rebuilds; the post is live in about a minute. Every post is a normal commit, so it can be edited or deleted like any other news file. The front matter records the author.
- Settings in Vercel (Project → Settings → Environment Variables), then redeploy:

| Variable | Value |
|---|---|
| `NEWS_USERS` | one `Name:password` per line (`Name:password:admin` for an administrator, who can edit or delete anyone's posts and pin notices), one per co-worker (removing a line signs that person out) |
| `NEWS_SECRET` | a long random string, e.g. the output of `openssl rand -base64 32` |
| `DEPLOY_HOOK_URL`, `CRON_SECRET` | daily rebuild so scheduled posts go out on their day (`docs/publishing.md`) |
| `GITHUB_TOKEN` | fine-grained token (github.com → Settings → Developer settings → Fine-grained tokens): repository `Omegaswitch/maltezskyrad` only, permission Contents: Read and write |
| `NEWS_NOTIFY`, `RESEND_API_KEY`, `MAIL_FROM` | optional: e-mail about every new post (Resend, as on lurdy.eu) |

- Drafts, scheduled posts, pinned notices, roles, the daily rebuild and the local stand-in (`node tests/news.local.js`) are described in `docs/publishing.md`.
- Test: `node tests/news.test.js` (GitHub stubbed). The editor is Quill 2.0.3 (BSD licence), in `static/js/vendor/quill-2.0.3/`.

**Service times, contacts, menu**
- Edit `content/site.json`.
- Calendar events live in AddCal (calendar `calendarGPB`) and appear on the site immediately, with no rebuild.

**Rules (from the Grand Magistry communications policy and coat-of-arms guidelines)**
- Use the full name of the Order at first mention, then "Suverénní maltézský řád" or "Maltézský řád".
- Never write "SMOM" or "Malta" on its own.
- Never add, redraw or recolour an emblem. Only the files listed in `docs/asset-manifest.md` may be used; `check.py` enforces this.
- Do not invent facts or figures. Link to orderofmalta.int for the Order's official texts.

**Publishing:** see `docs/deployment.md`. Production deployment needs the Grand Priory's authorisation.

## Documentation

- `PRODUCT.md`: purpose, audience, constraints.
- `DESIGN.md`: design system (tokens, type, components).
- `docs/content-inventory.md`: every page, its status, URL preservation and redirects.
- `docs/brand-compliance.md`: checklist against the official guidelines, deviations, open approvals.
- `docs/asset-manifest.md`: brand assets and what replaces each one.
- `docs/security-audit.md`: findings on the live site and the new implementation.
- `docs/qa-report.md`: what was tested and the results.
- `docs/qa-functional-audit-2026-10-18.md`: functional audit before the client presentation (routes, links, interactions, runtime), fixes and open items.
- `docs/deployment.md`: build, hosting, canonical host, launch checklist.
