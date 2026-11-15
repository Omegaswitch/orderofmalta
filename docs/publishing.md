# Publishing

The site is static. Everything the public sees is built by `build.py` from the files in `content/`. Staff publish through the editor at `/editor/`. The editor's API, `api/news.js`, writes the files into the repository `Omegaswitch/orderofmalta` as commits. Vercel then rebuilds the site.

The editor is English only. It is marked `noindex`, it is not linked from the site and it is not in the sitemap.

## Content types

| Type | Written to | Public address |
|---|---|---|
| News | `content/news/<lang>/<YYYY>/<file>.html` | `<news base><slug>/` |
| Press release | `content/press/<lang>/<YYYY>/<file>.html` | `<press base><slug>/` |
| Gallery (photo, album or video) | `content/galleries/<lang>/<YYYY>/<file>.html` | `<galleries base><slug>/` |

Each type can be written in any of the five languages: English (`en`, no prefix), Italian (`it`), French (`fr`), German (`de`) and Spanish (`es`). The section addresses for each language are in `docs/content-inventory.md`.

The editor writes only these paths and `static/media/<YYYY>/<MM>/`. Front matter follows `docs/build-spec.md`, section 3.2, and every file it writes has `"imported": false`.

## Translations

A post can be linked to its translation in another language. When a post is saved with `translationOf` set to the path of a post in another language, the two posts form one group. The `translations` map of every member of the group is updated in the same commit. The map always includes the post itself. Only languages with a real translation appear in it.

## Roles and sign-in

Sign-in uses Better Auth with e-mail and password. The users are stored in Postgres.

| Role | Access |
|---|---|
| `owner` | Same as `admin`, and can manage users through Better Auth (`api/_auth.mjs`). |
| `admin` | Writes and edits any post, and can pin notices. |
| `editor` | Writes posts. Edits only the posts it wrote or last edited, and posts with no author. The default role. |

- There is no self sign-up. Accounts are created by a command:

  ```sh
  npm run auth:user -- "Name" person@example.org 'a password of at least 12 characters' editor
  ```

  The role is `editor`, `admin` or `owner`. Run `npm run auth:migrate` once first to create the tables.
- Sessions last 12 hours.
- Sign-in requests are rate limited.
- Every write endpoint requires a signed-in user with a role that allows the action.

The legacy path (the `NEWS_USERS` list, where `Name:password:admin` makes an admin) is used only when `DATABASE_URL` is not set. It exists so that the tests and the local stand-in run without a database.

## Drafts, scheduling and pinned notices

- **Draft:** the post is saved and is not published. Drafts are listed in the editor and are not built.
- **Scheduled post:** a post with a future date is built on that day. The daily rebuild makes this happen (below).
- **Pinned notice:** the post shows on the home page and on the news listing of its own language, using the template's `pinned` flag. Only an admin or owner can pin a notice.
- **Editing:** editing keeps the post's address. The file records who edited it (`editedBy`).

## Daily rebuild

`vercel.json` defines a cron job that calls `/api/rebuild` every day at 03:00 UTC. That function asks a deploy hook to rebuild the site. Without `DEPLOY_HOOK_URL` the function does nothing.

The site's time zone is Europe/Rome.

## Environment variables

Set these in Vercel (Project, Settings, Environment Variables), then redeploy.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection string for Better Auth. |
| `BETTER_AUTH_SECRET` | Long random secret for Better Auth. Never put it in code. |
| `BETTER_AUTH_URL` | Public address of the site, used by Better Auth. |
| `GITHUB_TOKEN` | Fine-grained token for this repository only, with Contents: read and write. The editor commits posts with it. |
| `DEPLOY_HOOK_URL` | Deploy hook for the daily rebuild. |
| `CRON_SECRET` | Secret that Vercel sends with the cron call. When it is set, `/api/rebuild` refuses calls without it. |
| `NEWS_USERS`, `NEWS_SECRET` | Legacy sign-in, used only when `DATABASE_URL` is not set (tests and local use). |
| `RESEND_API_KEY` | Sends e-mail through Resend. Used by the GDPR form and by the optional new-post notice. |
| `NEWS_NOTIFY` | Optional. Addresses that get an e-mail about every change. No mail is sent without `RESEND_API_KEY` and `MAIL_FROM`. |
| `MAIL_FROM` | Sender address for e-mail. Required for any mail. |
| `GDPR_TO` | Recipient(s) of data-protection requests. No default: when it is unset the form answers with a configuration error. |

`GDPR_TO` and `MAIL_FROM` have no default in the code. The recipient address for data-protection requests is an open item (see `docs/legal-compliance.md`).

## Security

- **Sign-in:** Better Auth, with the sessions described above. The Better Auth tables are created by `npm run auth:migrate`.
- **Write endpoints:** every endpoint that writes content, or that sends e-mail, requires a signed-in user.
- **Text:** editor input is cleaned by a server-side allowlist. Scripts, styles, event handlers and other attributes are removed. Only the tags of the site's vocabulary (`docs/build-spec.md`, section 3.5) are kept. Embeds are kept only for YouTube and Vimeo addresses.
- **Files:** only the file types the site uses are accepted. Photos are saved under `static/media/<YYYY>/<MM>/`.
- **Paths:** the editor writes only under the paths in the table above and under `static/media/`.
- **Changes:** each save is a commit by the token in `GITHUB_TOKEN`, so the history shows every change and every change can be reverted.
- **Secrets:** they live only in environment variables. The site never echoes them.
- **Content Security Policy:** the headers in `vercel.json` allow scripts only from the site itself, and frames only from `www.youtube-nocookie.com` and `player.vimeo.com`.

See `docs/security-audit.md` for the status of the audit.

## Testing

- `node tests/news.test.js`: the editor API with GitHub stubbed. Covers sign-in, roles, drafts, scheduling, pinning, file checks, the sanitiser, the origin check, editing and deleting.
- `node tests/gdpr.test.js`: the data-protection request form.
- `node tests/news.local.js`: a local stand-in for the hosting. It serves `dist/` and the API, with GitHub replaced by this checkout, so the full flow can be tried in a browser. Build first with `python3 build.py`. Posts written this way land in `content/`. Discard them with `git checkout -- content static/media` when done.
- `python3 check.py`: the checks on `dist/`.

These tests have not yet been run against the production site. See `docs/qa-report.md`.
