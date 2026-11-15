# QA report

**QA for orderofmalta.int has not been run yet.** This file holds no results for this site. The template's QA report is not valid here and has been removed.

## What must be tested before launch

From the acceptance line of `docs/build-spec.md`:

1. `python3 build.py --offline && python3 check.py` passes with 0 problems.
2. `node tests/news.test.js && node tests/gdpr.test.js` pass.
3. Every live URL from the five sitemaps that is in the import scope answers 200 or a redirect in `python3 build.py serve`.
4. No request leaves the site's origin on any page before a visitor asks for an embed.

## Suggested additional checks (not yet agreed)

- Every section (home, news, press, galleries, pages) in all five languages, with the language switcher going to the real translation.
- Search in each language, with the index and the search page.
- Video embeds: click to load, the "always load" choice and the link without JavaScript.
- Gallery lightbox: keyboard, focus return, reduced motion.
- The editor: sign-in, roles, a draft, a scheduled post, a translation link, a pinned notice.
- The data-protection request form: validation, success and failure messages.
- The security headers on the deployed site.
- The 404 page for old addresses that are not imported yet.
- The results of the accessibility checks.

Results: none yet.
