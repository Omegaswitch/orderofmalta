# Functional audit

**QA for orderofmalta.int has not been run yet.** This file keeps its name from the template, where it recorded a functional audit of the template site on 18 October 2026. Those results are not valid for this site and have been removed.

## What must be tested

The tests are listed in `docs/qa-report.md`:

- The build and the checks (`python3 build.py --offline && python3 check.py`).
- The editor and GDPR tests (`node tests/news.test.js`, `node tests/gdpr.test.js`).
- Every live URL in the import scope answering 200 or a redirect in `python3 build.py serve`.
- No third-party request before a visitor asks for an embed.

Routes, links, interactions and runtime behaviour of this site have not been audited.

## Fixes and open items

None recorded yet.
