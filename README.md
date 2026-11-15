# orderofmalta.int

A rebuild of www.orderofmalta.int, the website of the Sovereign Military Hospitaller Order of St John of Jerusalem of Rhodes and of Malta (Sovereign Order of Malta), Grand Magistry. The site is in five languages: English (default), Italian, French, German and Spanish.

The rebuild uses the design system, security model and functions of the Czech Grand Priory site (maltezskyrad.cz). That site is the template for this one.

The site is static. A Python script (standard library and Pillow) turns the files in `content/` into HTML in `dist/`. Node is used only for the staff editor and the other serverless functions in `api/`. Hosting is Vercel.

Status: not launched. The live site is still WordPress. Do not move DNS or deploy to production until the launch gate in `docs/deployment.md` is met.

## Commands

```sh
python3 build.py                 # preview build into dist/ (noindex, status labels shown)
python3 build.py --production    # production build (indexable, no labels)
python3 build.py --offline       # build without any network access (also used by Vercel)
python3 build.py serve 8000      # preview build, then serve it at http://localhost:8000 (headers and redirects applied)
python3 check.py                 # checks dist/: broken links, brand assets, the forbidden acronym, javascript: links
python3 tools/import_oom.py --since 2025-01-01   # import content from the live site (items since the date)
node tests/news.test.js          # editor API tests (GitHub stubbed)
node tests/gdpr.test.js          # GDPR form tests
npm run auth:migrate             # create the Better Auth tables in Postgres (needs DATABASE_URL)
npm run auth:user                # add a staff account: node scripts/add-user.mjs "Name" email password [editor|admin|owner]
```

Use `--since 2015-01-01` to import the full archive with the same code. See `docs/content-inventory.md` for the import scope.

## Where things are

| Path | What |
|---|---|
| `content/pages/<lang>/<path>/index.html` | Pages. Each file has JSON front matter between `---` lines, then HTML. The URL is the original live path. |
| `content/news/<lang>/<YYYY>/<file>.html` | News items. |
| `content/press/<lang>/<YYYY>/<file>.html` | Press releases. |
| `content/galleries/<lang>/<YYYY>/<file>.html` | Photo and video galleries. |
| `content/collections/<lang>/` | `publications.json` and `in-the-news.json`, rendered on their pages. |
| `content/menus.json` | Main menu, footer menu, social links and legal links, per language. |
| `content/translations/categories.json` | News categories, with the term in each language. |
| `content/redirects.json` | Redirects found while importing (exact paths). |
| `content/media-map.json` | Import state: source URL to local media file. |
| `content/site.json` | Site identity, languages, time zone, section URLs, contact details. |
| `content/i18n.json` | Interface strings in en, it, fr, de and es. |
| `static/` | CSS, JS, fonts, official brand files (`img/`) and migrated media (`media/`). |
| `static/media/` | Photos and documents imported from the live site. |
| `api/` | Serverless functions: staff sign-in, editor API, GDPR request form, daily rebuild. |
| `templates/editor.html` | The staff editor page (`/editor/`). |
| `scripts/` | `add-user.mjs` (add a staff account), `auth-schema.sql`, `user-sql.mjs`. |
| `tests/` | `news.test.js`, `gdpr.test.js`, and `news.local.js` (a local stand-in for the hosting). |
| `tools/` | `import_oom.py` (importer), `make_lockup.py` (lockups), `make_og.py` (link-preview cards). |
| `vercel.json` | Hosting settings, security headers, cron job and pattern redirects. |
| `build.py`, `check.py` | The build and the checks. |
| `DESIGN.md` | The design system (tokens, type, components). |
| `docs/` | Documentation (see below). |

## World map

The home page ("activities in 130 countries") and the Contacts pages show an interactive map (`static/js/map.js`, styles at the end of `static/css/site.css`, strings `map*` in `content/i18n.json`). Its data is generated, not hand-edited:

```sh
mkdir /tmp/atlas && curl -L https://registry.npmjs.org/world-atlas/-/world-atlas-2.0.2.tgz | tar xz -C /tmp/atlas
python3 -I tools/make_map.py /tmp/atlas/package/countries-50m.json     # add -v to list how the headings were matched
```

This writes `static/map/world.svg` (Equal Earth projection, Antarctica dropped, markers for microstates) and `static/map/presence.<lang>.json` (entities per country, parsed from the imported Contacts pages; nothing is added that is not on those pages). Re-run it after the Contacts pages are re-imported. Country names are matched across languages through the e-mail addresses and web hosts the entries share (the headings are sorted differently in each language); mismatches are logged.

Geometry: Natural Earth (public domain) via the npm package `world-atlas` 2.0.2, `countries-50m.json` (ISC licence). The package is not kept in the repository.

## Editorial workflow

Staff publish at `/editor/`. The page is in English only. It is not linked from the site, it is marked `noindex` and it is not in the sitemap.

- **Content types:** news, press releases and photo or video galleries. Each item can be written in any of the five languages.
- **Accounts:** there is no self sign-up. An owner, an admin or an editor account is created with `npm run auth:user`. Sign-in uses Better Auth with e-mail and password, and the users are stored in Postgres. Sessions last 12 hours.
- **Roles:** `owner`, `admin` and `editor`.
- **Drafts and scheduling:** a post can be saved as a draft. A post with a future date goes live on that day, because the daily rebuild runs at 03:00 UTC. Dates and times are in the Europe/Rome time zone.
- **Pinned notices:** a pinned item shows on the home page and on the news listing of its own language.
- **Translations:** a post in one language can be linked to its translation in another language. The links are stored in the `translations` map of every post in the group.
- **Imported files:** a file that is edited by hand or in the editor is saved with `"imported": false`. The importer never overwrites such a file.

The full description is in `docs/publishing.md`.

## Rules

- Never write the four-letter acronym of the Order's name. Use the full name, or the short name given in `content/site.json`.
- Use only the official brand files listed in `docs/asset-manifest.md`. `check.py` checks the image paths.
- Never add, redraw or recolour an emblem.
- Never invent facts, figures, names or approvals. If something is not known, say so in the text or in the docs.
- Keep the security model: a strict Content Security Policy, no inline scripts or event handlers, sanitised editor input, and authentication on every write endpoint.
- Read `docs/build-spec.md` before any change. It is the contract between the parts of the project.

## Documentation

- `PRODUCT.md`: purpose, audiences, languages and constraints.
- `DESIGN.md`: design system (tokens, type, components).
- `docs/build-spec.md`: the build contract (URLs, content formats, interfaces).
- `docs/content-inventory.md`: content types, URL scheme, import scope, what is dropped and why, redirects.
- `docs/publishing.md`: the editor, roles, languages, environment variables, daily rebuild, security and tests.
- `docs/deployment.md`: build, hosting, canonical host, launch gate and launch checklist.
- `docs/asset-manifest.md`: brand assets and the open items on them.
- `docs/brand-compliance.md`: brand rules and open approvals.
- `docs/security-audit.md`: the security design and the audit status.
- `docs/legal-compliance.md`: privacy, cookies and legal points, and open items.
- `docs/qa-report.md`, `docs/qa-functional-audit-2026-10-18.md`: QA status (not yet run for this site).

The site was built from the template at `maltezskyrad.cz`. That project's documents describe the Czech site and are not valid for this one.
