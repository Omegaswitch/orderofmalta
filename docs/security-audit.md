# Security and privacy

**Status: the audit of this site has not been run yet. It must be re-run for this site before launch.** The findings of the template's audit (of the template site) are not valid for this site and have been removed. The live site at www.orderofmalta.int is WordPress, and the notes below record only what was observed while scouting it.

## Design of the new site

- **Static output:** the pages, CSS and JS are built by `build.py` and served as files. Visitors do not run server code.
- **Serverless functions (`api/`):** the staff editor and its API, the data-protection request form, and the daily rebuild. Node packages: `better-auth` and `pg`.
- **Staff sign-in:** Better Auth with e-mail and password, users and sessions in Postgres, roles owner, admin and editor, no self sign-up, sessions of 12 hours, rate limiting.
- **No cookies and no analytics:** the site sets no cookies. Google Tag Manager is dropped. The only browser storage is the video consent key (see below).
- **Build:** the build never touches the network (`--offline` is accepted and the build runs without it).

## Content handling

- **Importer:** writes only the body vocabulary in `docs/build-spec.md`, section 3.5. Scripts, event handlers, styles, iframes and unknown markup are not written. The importer lists pages whose body still has unmapped markup in its report.
- **Editor input:** cleaned on the server by an allowlist. Scripts, styles, event handlers and foreign attributes are removed. The only embeds allowed are YouTube and Vimeo addresses.
- **`check.py`:** fails the build for any `javascript:` link, any broken internal link, any image under `/img/` that is not an approved brand file, and the forbidden acronym in page text.
- **Search:** the search page builds result items with `textContent` and `createElement`. It never uses `innerHTML` with index data.

## Headers

Defined in `vercel.json` and written to `dist/_headers` by the build. Applied to every path.

| Header | Value |
|---|---|
| `Content-Security-Policy` | `default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; worker-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; frame-src https://www.youtube-nocookie.com https://player.vimeo.com; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'; upgrade-insecure-requests` |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` |
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()` |
| `Cross-Origin-Opener-Policy` | `same-origin` |
| `X-Frame-Options` | `DENY` |

Notes:

- Compared with the template, the AddCal hosts are removed from every directive, and `frame-src` allows the YouTube and Vimeo players instead. `img-src`, `font-src` and `connect-src` no longer name any third party.
- `style-src` allows `'unsafe-inline'`. It is kept from the template and is not yet re-checked for this site.
- `'wasm-unsafe-eval'` is kept from the template, where the template uses it for PDF compression in its staff page. Whether it is still needed on this site is open.
- Images are local, so `img-src` needs no third party.

## Embeds and third parties

- **Before a visitor asks:** no request leaves the site's origin on any page. Embeds show a poster and a button.
- **After a click:** the video loads from `youtube-nocookie.com` or `player.vimeo.com`. Those services may set their own cookies.
- **Consent for videos:** "Always load videos" stores the list of providers in `localStorage` under `oom-embed-consent`. This is not a cookie and it is sent nowhere. The visitor can clear it in the browser.
- **Server-side services:** Better Auth and Postgres (sign-in), GitHub (the editor commits), Resend (e-mail for the data-protection form and the optional new-post notice), Vercel (hosting and the cron job).

## Secrets

- Credentials and keys are environment variables only (see `docs/publishing.md`).
- Nothing in the repository or the built pages should contain a token. This has not yet been scanned for this site.

## Supply chain

- Build: Python 3 standard library and Pillow.
- Functions: `better-auth` and `pg`, pinned in `package-lock.json`.
- Developer tools only: Playwright, for `tools/make_og.py`.
- Still to do: a dependency audit of the Node packages, and a check of the pinned versions.

## Observations on the live site (scouting, not an audit)

Scouted on 15 Nov 2026. These are notes, not findings.

- WordPress with the WPML language plugin, a theme, and Popup Maker, Google Tag Manager, Relevanssi search, Yoast and Cloudflare e-mail obfuscation.
- The REST API answers publicly for pages, media and news. `/wp-json/wp/v2/menus` answers 401.
- The theme loads jQuery, Bootstrap, Owl and Fancybox.
- The site sends a Google Tag Manager container and a pop-up for the app.

The new site drops all of these.

## Re-check for this site (to be run)

- Run the audit on the built `dist/` and on the deployed site.
- Check the headers on the deployed host (`curl -I`).
- Scan the repository and the build output for secrets.
- Review the Better Auth configuration, the editor's sanitiser and the rate limits.
- Review whether `'unsafe-inline'` in `style-src` and `'wasm-unsafe-eval'` are still needed.
- Run a dependency audit on `package-lock.json`.
