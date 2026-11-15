# Deployment

**Nothing deploys to production, and the live site at www.orderofmalta.int is not changed, until the launch gate and the launch checklist below are complete and the Grand Magistry has approved the launch.** The repository does not deploy by itself.

## Build

```sh
python3 build.py                 # preview: noindex everywhere, status labels shown
python3 build.py --production    # production: indexable, no status labels
python3 build.py --offline       # build without network access (what Vercel runs)
python3 check.py                 # must report 0 problems before anything is published
```

The build needs Python 3 with Pillow. The output is `dist/`, a static folder with HTML, CSS, JS, fonts, media, the sitemap, the feeds, `robots.txt`, `_headers` and `_redirects`.

Node is needed only for `api/`, `scripts/` and `tests/`. Install the Node packages with `npm ci`.

## Hosting on Vercel

`vercel.json` holds the Vercel settings:

| Setting | Value |
|---|---|
| Install command | `npm ci` |
| Build command | `python3 build.py --production --offline` |
| Output directory | `dist` |
| Cron job | `/api/rebuild` at `0 3 * * *` (03:00 UTC every day) |

The same file holds the security headers (Content Security Policy, HSTS, nosniff, Referrer-Policy, Permissions-Policy, COOP and X-Frame-Options) and the redirects. Vercel reads these from `vercel.json`. The build also writes `dist/_headers` and `dist/_redirects` for other hosts and for the local preview server.

Other hosts (Netlify, Cloudflare Pages, or the own server) can use `dist/_headers` and `dist/_redirects` as the template does. Apply the same headers.

## Environment variables

Set these in the Vercel project, then redeploy. The full list and what each one does is in `docs/publishing.md`.

- `DATABASE_URL`, `BETTER_AUTH_SECRET`, `BETTER_AUTH_URL`: staff sign-in.
- `GITHUB_TOKEN`: the editor's commits.
- `DEPLOY_HOOK_URL`, `CRON_SECRET`: the daily rebuild.
- `RESEND_API_KEY`, `MAIL_FROM`, `GDPR_TO`: the data-protection request form. `GDPR_TO` and `MAIL_FROM` have no default. Without them the form answers with a configuration error.
- `NEWS_NOTIFY`: optional notice e-mail.

## Canonical host

The canonical address is `https://www.orderofmalta.int` (`baseUrl` in `content/site.json`). Canonical links, the sitemap and the Open Graph tags use it.

Decide before launch how the apex host (`orderofmalta.int`) and any other host reach it. Make sure the certificate covers every name that is served.

## Better Auth migration

Staff sign-in needs its tables in Postgres:

1. Set `DATABASE_URL` and `BETTER_AUTH_SECRET`.
2. Run `npm run auth:migrate` once.
3. Create the first owner: `npm run auth:user -- "Name" person@example.org 'a password of at least 12 characters' owner`.
4. Check that `/editor/` signs in and that the account can save a draft.

There is no self sign-up. Users are created with `npm run auth:user`.

## Launch gate

The archive is not complete yet. Items before 1 Jan 2025 are not imported (`docs/content-inventory.md`). Before the DNS moves to this site, one of these must be true:

1. **Full archive import:** run `python3 tools/import_oom.py --since 2015-01-01`, check the report, and build again. Every old news, press and gallery address then answers with its item.
2. **Legacy host:** keep the old WordPress site on a legacy host. Add after-filesystem `rewrites` to `vercel.json` for the `news`, `press` and `galleries` bases of each language, so that old addresses that are not in the import go to that host.

`check.py` reports internal links into those three bases that do not resolve. It reports them as a count, as warnings, not as failures. Use the count to judge how much is missing.

## Content redirects

`content/redirects.json` holds the redirects found while importing. The build writes a stub page for each one and adds them to `dist/_redirects`. If the file is small (fewer than 500 entries), fold it into `vercel.json` as ordinary redirects, so that every host gets them from one place. If it is larger, keep it as the build's file.

## Launch checklist

1. Resolve the open items in `docs/brand-compliance.md` and `docs/asset-manifest.md`. In particular, the outlined lockups need the licensed font and the Grand Magistry's approval.
2. Confirm the open legal items in `docs/legal-compliance.md`, including the address that receives data-protection requests and the approval of the privacy and cookie pages.
3. Pass the launch gate above.
4. Run `python3 tools/import_oom.py --since 2025-01-01` if the content is not yet current, then `python3 build.py --production` and `python3 check.py`. The check must report 0 problems.
5. Run `node tests/news.test.js` and `node tests/gdpr.test.js`.
6. Complete the Better Auth migration and sign in as the owner.
7. Set the environment variables on Vercel and redeploy.
8. Verify on the deployed site:
   - the security headers are sent on `/` (`curl -I`);
   - the old paths from the content inventory answer 200 or a redirect;
   - `/editor/` is not in the sitemap and sends `noindex`;
   - the daily rebuild runs after 03:00 UTC (check the deployment list on Vercel the next day).
9. Submit `https://www.orderofmalta.int/sitemap.xml` to the search engines.
10. Before the WordPress site is switched off, keep a full backup of its database and `wp-content`. When and how the old site is retired is open. The Grand Magistry decides it.

Items 1 to 3 and the launch decision are open. Nothing in this repository has been run against the production site.
