# Graph Report - orderofmalta  (2026-11-15)

## Corpus Check
- 73 files · ~1,513,258 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 26 file(s) not represented in the graph (top: .woff2 16, (none) 3, .zip 3)

## Summary
- 1429 nodes · 3143 edges · 74 communities (60 shown, 14 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 176 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c9410949`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- news-editor.js
- quill.js
- import_oom.py
- m
- i
- Importer
- check.py
- o
- esc
- Body
- news.js
- build
- Components
- .news_item
- optimize
- make_map.py
- jt
- build
- s
- N
- h
- build.py
- c
- 3. Content model
- Module
- Node
- render_page
- _auth.mjs
- href_attr
- b
- update
- ci.yml
- render_news
- qt
- publish
- remove
- Product
- news.local.js
- news.test.js
- Media
- env
- api/gdpr.js
- vercel.json
- children_of
- Deployment
- Publishing
- Security and privacy
- search.js
- X
- .Cb
- N
- u
- Content inventory
- Critique: homepage hero photo integration
- orderofmalta.int
- site.js
- E
- Q
- serve
- Asset manifest
- Legal and privacy compliance
- user-sql.mjs
- k
- Brand compliance
- Functional audit
- QA report
- CLAUDE.md
- index-html.md
- bb

## God Nodes (most connected - your core abstractions)
1. `esc()` - 58 edges
2. `i` - 57 edges
3. `Module()` - 50 edges
4. `s` - 43 edges
5. `Importer` - 43 edges
6. `build()` - 40 edges
7. `o` - 39 edges
8. `m` - 38 edges
9. `render_page()` - 33 edges
10. `layout()` - 31 edges

## Surprising Connections (you probably didn't know these)
- `5.1 Page frame` --references--> `crumbs_html()`  [INFERRED]
  docs/build-spec.md → build.py
- `2. Languages and URLs` --references--> `s`  [INFERRED]
  docs/build-spec.md → static/js/vendor/quill-2.0.3/quill.js
- `3.8 Importer command` --references--> `_self_test()`  [INFERRED]
  docs/build-spec.md → tools/import_oom.py
- `5.7 Staff editor and API` --references--> `slugify()`  [INFERRED]
  docs/build-spec.md → api/news.js
- `5.7 Staff editor and API` --references--> `publish()`  [INFERRED]
  docs/build-spec.md → api/news.js

## Import Cycles
- None detected.

## Communities (74 total, 14 thin omitted)

### Community 0 - "news-editor.js"
Cohesion: 0.08
Nodes (65): allPosts(), applyType(), attachmentRow(), attr(), authJson(), block(), blocks(), btn() (+57 more)

### Community 1 - "quill.js"
Cohesion: 0.05
Nodes (34): add(), buildItem(), buildLabel(), buildOptions(), buildPicker(), close(), constructor(), copy() (+26 more)

### Community 2 - "import_oom.py"
Cohesion: 0.06
Nodes (31): category_sitemap_redirects(), clean_switcher(), convert_app(), date_iso(), dmy_to_iso(), drop_title_heading(), dump_front(), file_slug() (+23 more)

### Community 3 - "m"
Cohesion: 0.06
Nodes (8): attachUI(), descendant(), et, getHTML(), m, nt(), query(), rt

### Community 4 - "i"
Cohesion: 0.06
Nodes (4): getText(), handleDOM(), i, U()

### Community 5 - "Importer"
Cohesion: 0.09
Nodes (8): Http, Importer, find(), union(), fix(), main(), note(), write_text_if_changed()

### Community 6 - "check.py"
Cohesion: 0.07
Nodes (20): check_page(), main(), Page, redirect_sources(), resolves(), line(), main(), bbox() (+12 more)

### Community 7 - "o"
Cohesion: 0.09
Nodes (16): applyDelta(), attach(), d(), deleteText(), f, formatLine(), formatText(), handler() (+8 more)

### Community 8 - "esc"
Cohesion: 0.12
Nodes (30): _attrs(), auto_srcset(), card_html(), embed_html(), enhance_body(), expand_embeds(), one(), _fix_img() (+22 more)

### Community 9 - "Body"
Cohesion: 0.16
Nodes (7): abs_url(), attr_text(), Body, flush(), convert_fragment(), decode_cfemail(), esc_attr()

### Community 10 - "news.js"
Cohesion: 0.06
Nodes (29): ALLOWED, authRoles, BASE_URL, BASES, CATEGORY_FILE, crypto, DIR, DOMAIN (+21 more)

### Community 11 - "build"
Cohesion: 0.11
Nodes (31): build(), chunk(), crumbs_html(), footer_more(), gallery_type_url(), home_url(), lang_of_path(), lang_switch() (+23 more)

### Community 12 - "Components"
Cohesion: 0.06
Nodes (34): Article and body vocabulary, Buttons, Cards (flat, editorial), Colors, Components, Content-status bar (preview only), Content-status (preview only), Design System: orderofmalta.int (+26 more)

### Community 13 - ".news_item"
Cohesion: 0.13
Nodes (9): Doc, local_path(), text_excerpt(), trunc(), upload_rel(), utc_to_local(), watch_url(), with_slash() (+1 more)

### Community 14 - "optimize"
Cohesion: 0.09
Nodes (17): appendChild(), deleteAt(), descendants(), enforceAllowedChildren(), format(), formatAt(), insertAt(), isolate() (+9 more)

### Community 15 - "make_map.py"
Cohesion: 0.12
Nodes (21): antimeridian_pieces(), build_geometry(), build_presence(), case_word(), classify(), clean(), clip_lon(), decode_arcs() (+13 more)

### Community 16 - "jt"
Cohesion: 0.11
Nodes (22): Bt(), Ct(), Dt(), Et(), F(), Ft(), Gt(), It() (+14 more)

### Community 17 - "build"
Cohesion: 0.14
Nodes (28): build(), anchored(), animateTo(), apply(), bboxCentre(), closePanel(), ctl(), doGesture() (+20 more)

### Community 18 - "s"
Cohesion: 0.11
Nodes (3): register(), s, wrap()

### Community 19 - "N"
Cohesion: 0.11
Nodes (4): N, q(), R(), w()

### Community 21 - "build.py"
Cohesion: 0.13
Nodes (15): alt_links(), alts_for(), _content_path(), due(), editor_posts(), _image_info(), jsonld_org(), load_items() (+7 more)

### Community 22 - "c"
Cohesion: 0.12
Nodes (3): c, clone(), j

### Community 23 - "3. Content model"
Cohesion: 0.09
Nodes (22): 0. What the live site is (scouted 15 Nov 2026), 1. Feature inventory, 2. Languages and URLs, 3.1 Files, 3.2 Front matter (exact keys), 3.3 Categories (`content/translations/categories.json`), 3.4 Menus (`content/menus.json`), 3.5 Body HTML vocabulary (+14 more)

### Community 24 - "Module"
Cohesion: 0.12
Nodes (9): Module(), Aa(), eb(), fb(), R(), ub(), wa(), ya() (+1 more)

### Community 25 - "Node"
Cohesion: 0.13
Nodes (4): _Builder, Node, rec(), parse()

### Community 26 - "render_page"
Cohesion: 0.16
Nodes (18): by_lang(), collection_filter(), contacts_tabs(), cutting_card(), summary(), hub_html(), page_card(), plain() (+10 more)

### Community 27 - "_auth.mjs"
Cohesion: 0.12
Nodes (16): ac, auth, roles, trustedOrigins, dependencies, better-auth@^1.7.22, pg@^8.23.1, description (+8 more)

### Community 28 - "href_attr"
Cohesion: 0.19
Nodes (18): _footer_clean(), collect(), walk(), footer_cols(), href_attr(), is_external(), legal_links(), link_li() (+10 more)

### Community 29 - "b"
Cohesion: 0.19
Nodes (6): b(), find(), g(), getFormat(), n(), O()

### Community 30 - "update"
Cohesion: 0.15
Nodes (16): A(), a, build(), create(), getDelta(), getRange(), I(), e() (+8 more)

### Community 31 - "ci.yml"
Cohesion: 0.12
Nodes (16): runs-on, steps, jobs, build, name, on, pull_request, push (+8 more)

### Community 32 - "render_news"
Cohesion: 0.18
Nodes (13): cat_descendants(), cat_members(), cat_name(), cat_term(), cat_url(), cat(), pub_tabs(), redirect_entries() (+5 more)

### Community 33 - "qt"
Cohesion: 0.29
Nodes (3): hide(), qt(), St()

### Community 34 - "publish"
Cohesion: 0.18
Nodes (14): canonicalVideo(), embedUrl(), esc(), excerptOf(), galleryOf(), oneLine(), plain(), publish() (+6 more)

### Community 35 - "remove"
Cohesion: 0.21
Nodes (14): editable(), join(), load(), mayChange(), mayRetarget(), members(), notify(), parsePath() (+6 more)

### Community 36 - "Product"
Cohesion: 0.14
Nodes (13): Accessibility & Inclusion, Brand Commitments, Capabilities and Constraints, Evidence on Hand, Names, Operating Context, Platform, Positioning (+5 more)

### Community 37 - "news.local.js"
Cohesion: 0.14
Nodes (8): blobs, crypto, fs, http, path, port, ROOT, TYPES

### Community 38 - "news.test.js"
Cohesion: 0.14
Nodes (5): assert, CATS, commits, png, stored

### Community 40 - "env"
Cohesion: 0.24
Nodes (13): betterAuth(), commit(), contentsPath(), env(), exists(), gh(), locate(), same() (+5 more)

### Community 41 - "api/gdpr.js"
Cohesion: 0.18
Nodes (6): esc(), FORMS, message(), assert, ok, sent

### Community 42 - "vercel.json"
Cohesion: 0.17
Nodes (11): buildCommand, cleanUrls, crons, framework, headers, installCommand, outputDirectory, redirects (+3 more)

### Community 43 - "children_of"
Cohesion: 0.24
Nodes (8): children_of(), derive_main(), menu_label(), walk(), nav_label(), page_trail(), side_nav(), walk()

### Community 44 - "Deployment"
Cohesion: 0.20
Nodes (9): Better Auth migration, Build, Canonical host, Content redirects, Deployment, Environment variables, Hosting on Vercel, Launch checklist (+1 more)

### Community 45 - "Publishing"
Cohesion: 0.20
Nodes (9): Content types, Daily rebuild, Drafts, scheduling and pinned notices, Environment variables, Publishing, Roles and sign-in, Security, Testing (+1 more)

### Community 46 - "Security and privacy"
Cohesion: 0.20
Nodes (9): Content handling, Design of the new site, Embeds and third parties, Headers, Observations on the live site (scouting, not an audit), Re-check for this site (to be run), Secrets, Security and privacy (+1 more)

### Community 47 - "search.js"
Cohesion: 0.40
Nodes (9): dateText(), find(), fold(), item(), load(), marked(), ranges(), search() (+1 more)

### Community 49 - ".Cb"
Cohesion: 0.28
Nodes (8): c(), d(), I, jb(), kb(), lb(), mb(), qb()

### Community 50 - "N"
Cohesion: 0.36
Nodes (9): hb(), ib(), M(), N(), O(), P(), Q(), rb() (+1 more)

### Community 52 - "Content inventory"
Cohesion: 0.25
Nodes (7): Content inventory, Content types, Import scope, Open items, Redirects, URL scheme, What is dropped, and why

### Community 53 - "Critique: homepage hero photo integration"
Cohesion: 0.25
Nodes (7): Critique: homepage hero photo integration, Design Health Score, Design specificity, Minor observations, Persona red flags, Priority issues, Questions

### Community 54 - "orderofmalta.int"
Cohesion: 0.25
Nodes (7): Commands, Documentation, Editorial workflow, orderofmalta.int, Rules, Where things are, World map

### Community 55 - "site.js"
Cohesion: 0.48
Nodes (6): allow(), buildBox(), consented(), go(), pause(), restart()

### Community 56 - "E"
Cohesion: 0.33
Nodes (6): a(), sa(), Ta(), ua(), va(), E()

### Community 58 - "serve"
Cohesion: 0.70
Nodes (5): serve(), do_GET(), end_headers(), guess_type(), _redirect()

### Community 59 - "Asset manifest"
Cohesion: 0.40
Nodes (4): Asset manifest, Files to remove from the scaffold, Not on the site, and not to be created, Photographs and documents from the live site

### Community 60 - "Legal and privacy compliance"
Cohesion: 0.40
Nodes (4): Legal and privacy compliance, Open items, Operator details, Points by topic

### Community 64 - "Brand compliance"
Cohesion: 0.50
Nodes (3): Brand compliance, Open approvals, Rules for this site

### Community 65 - "Functional audit"
Cohesion: 0.50
Nodes (3): Fixes and open items, Functional audit, What must be tested

### Community 66 - "QA report"
Cohesion: 0.50
Nodes (3): QA report, Suggested additional checks (not yet agreed), What must be tested before launch

### Community 69 - "bb"
Cohesion: 0.67
Nodes (3): bb(), cc(), a()

## Knowledge Gaps
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `s` connect `s` to `quill.js`, `m`, `i`, `o`, `jt`, `u`, `h`, `3. Content model`, `b`, `update`?**
  _High betweenness centrality (0.276) - this node is a cross-community bridge._
- **Are the 45 inferred relationships involving `esc()` (e.g. with `build()` and `card_html()`) actually correct?**
  _`esc()` has 45 INFERRED edges - model-reasoned connections that need verification._
- **Should `news-editor.js` be split into smaller, more focused modules?**
  _Cohesion score 0.0782608695652174 - nodes in this community are weakly interconnected._
- **Why does `2. Languages and URLs` connect `3. Content model` to `s`?**
  _High betweenness centrality (0.253) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `Module()` (e.g. with `ac()` and `$b()`) actually correct?**
  _`Module()` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Should `quill.js` be split into smaller, more focused modules?**
  _Cohesion score 0.04811507936507937 - nodes in this community are weakly interconnected._
- **Are the 2 inferred relationships involving `s` (e.g. with `2. Languages and URLs` and `l()`) actually correct?**
  _`s` has 2 INFERRED edges - model-reasoned connections that need verification._