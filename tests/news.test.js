// Checks api/news.js with GitHub stubbed: sign-in and roles, file checks, cleaning of the text (embed allowlist),
// the committed post in five languages and three types, translation linking, drafts and scheduling, pinning,
// the paths the API may write to, and what an editor may not do.
//   node tests/news.test.js
const assert = require("assert");
process.env.NEWS_USERS = "Anna:secret-pass-1:admin\nPiero:other-pass-2\nOtto:third:pass";  // a password may hold a colon
process.env.NEWS_SECRET = "test-secret";
process.env.GITHUB_TOKEN = "test-token";
delete process.env.DATABASE_URL;
delete process.env.MAIL_FROM;
const handler = require("../api/news.js");
const HOST = "www.orderofmalta.int";
const CATS = Object.keys(require("../content/translations/categories.json"));
const CAT = CATS.find((c) => c !== "all-news") || "all-news";

const commits = [];
const stored = {};  // files the stubbed repository holds, by path
global.fetch = async (url, opts = {}) => {
  const u = new URL(url), body = opts.body ? JSON.parse(opts.body) : null;
  const json = (status, data) => ({ ok: status < 300, status, json: async () => data });
  if (u.hostname === "api.resend.com") return json(200, {});
  if (u.pathname.includes("/contents/")) {
    const p = decodeURIComponent(u.pathname.split("/contents/")[1]);
    if (p in stored) return json(200, { content: Buffer.from(stored[p]).toString("base64") });
    const kids = [...new Set(Object.keys(stored).filter((k) => k.startsWith(p + "/")).map((k) => k.slice(p.length + 1).split("/")[0]))];
    if (kids.length) return json(200, kids.map((name) => ({ name, type: Object.keys(stored).includes(`${p}/${name}`) ? "file" : "dir" })));
    return json(404, {});
  }
  if (u.pathname.endsWith("/git/blobs")) return json(201, { sha: "a".repeat(40) });
  if (u.pathname.endsWith("/git/ref/heads/main")) return json(200, { object: { sha: "c".repeat(40) } });
  if (/\/git\/commits\/c+$/.test(u.pathname)) return json(200, { tree: { sha: "t".repeat(40) } });
  if (u.pathname.endsWith("/git/trees")) {
    commits.push(body.tree);
    for (const f of body.tree) if (f.content != null) stored[f.path] = f.content; else if (f.sha === null) delete stored[f.path];  // the stub keeps the repository's state
    return json(201, { sha: "n".repeat(40) });
  }
  if (u.pathname.endsWith("/git/commits")) { commits.messages = (commits.messages || []).concat(body.message); return json(201, { sha: "d".repeat(40) }); }
  if (u.pathname.endsWith("/git/refs/heads/main")) return json(200, {});
  throw new Error("unexpected " + url);
};

function call(method, body, cookie, headers = {}) {
  return new Promise((done) => {
    const h = { host: HOST, origin: `https://${HOST}`, ...(cookie ? { cookie } : {}), ...headers };
    const res = { statusCode: 200, h: {}, setHeader(k, v) { this.h[k.toLowerCase()] = v; }, end(s) { done({ status: this.statusCode, body: JSON.parse(s || "{}"), cookie: this.h["set-cookie"] }); } };
    handler({ method, headers: h, body }, res);
  });
}
const meta = (doc) => JSON.parse(doc.split("---\n")[1]);
const lastCommit = () => commits[commits.length - 1];
const fileOf = (tree, path) => (tree.find((f) => f.path === path) || {}).content;
const seed = (path, m, body = "<p>Text.</p>\n") => { stored[path] = `---\n${JSON.stringify(m, null, 1)}\n---\n${body}`; };
const png = Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47]), Buffer.alloc(20)]).toString("base64");
const post = (extra) => ({ action: "publish", title: "Title", date: "2026-11-02T10:30", body: "<p>Text.</p>", ...extra });

(async () => {
  const { sanitise, slugify, users, canonicalVideo, parsePath, stemOf } = handler;

  // ---- sanitiser
  assert.strictEqual(sanitise('<p onclick="x()">A <b>B</b><script>evil()</script></p>'), "<p>A <strong>B</strong></p>");
  assert.strictEqual(sanitise('<p><a href="javascript:alert(1)">x</a> <a href="https://a.org/" target="_blank">y</a></p>'), '<p>x <a href="https://a.org/">y</a></p>');
  assert.strictEqual(sanitise('<h1 style="font-size:90px">T</h1><p><img src="data:x"><img src="/media/2026/10/a-1.webp" onerror="x"></p>'), '<h2>T</h2><p><img src="/media/2026/10/a-1.webp" alt=""></p>');
  assert.strictEqual(sanitise('<p><img src="/media/../../etc/passwd"><img src="https://evil.example/x.png"></p>'), "");
  assert.strictEqual(sanitise("<p>1 < 2 &amp; 3&nbsp;4</p><p></p><p><br></p>"), "<p>1 &lt; 2 &amp; 3 4</p>");
  assert.match(sanitise("<ul><li>a<li>b</ul><p>c"), /<\/ul><p>c<\/p>$/);  // unclosed tags are closed
  assert.strictEqual(sanitise('<p><a href="https://a.org/?x=1&amp;y=2">q</a></p>'), '<p><a href="https://a.org/?x=1&amp;y=2">q</a></p>');  // entities are not doubled
  assert.strictEqual(sanitise('<p><iframe src="https://www.youtube.com/embed/x"></iframe>v</p><p style="x" id="y" data-a="1">w</p>'), "<p>v</p><p>w</p>");
  // embeds: only YouTube and Vimeo watch links in <p class="embed">; any other class is dropped
  assert.strictEqual(sanitise('<p class="embed"><a href="https://www.youtube.com/watch?v=dQw4w9WgXcQ">Clip</a></p>'), '<p class="embed"><a href="https://www.youtube.com/watch?v=dQw4w9WgXcQ">Clip</a></p>');
  assert.strictEqual(sanitise('<p class="embed"><a href="https://youtu.be/dQw4w9WgXcQ">Clip</a></p>'), '<p class="embed"><a href="https://youtu.be/dQw4w9WgXcQ">Clip</a></p>');
  assert.strictEqual(sanitise('<p class="embed"><a href="https://vimeo.com/123456789">Film</a></p>'), '<p class="embed"><a href="https://vimeo.com/123456789">Film</a></p>');
  assert.strictEqual(sanitise('<p class="embed"><a href="https://evil.example/watch?v=dQw4w9WgXcQ">Clip</a></p>'), "<p>Clip</p>");  // wrong host: no link, no embed
  assert.strictEqual(sanitise('<p class="embed"><a href="https://www.youtube.com.evil.example/watch?v=dQw4w9WgXcQ">Clip</a></p>'), "<p>Clip</p>");
  assert.strictEqual(sanitise('<p class="embed"><a href="https://vimeo.com/123/../x">Film</a></p>'), "<p>Film</p>");
  assert.strictEqual(sanitise('<p class="embed"><a href="http://www.youtube.com/watch?v=dQw4w9WgXcQ">Clip</a></p>'), "<p>Clip</p>");  // https only
  assert.strictEqual(sanitise('<p class="embed"><a href="javascript:alert(1)">Clip</a></p>'), "<p>Clip</p>");
  assert.strictEqual(sanitise('<p class="embed hero" onclick="x"><a href="https://www.youtube.com/watch?v=dQw4w9WgXcQ">Clip</a></p>'), '<p><a href="https://www.youtube.com/watch?v=dQw4w9WgXcQ">Clip</a></p>');  // not the embed class: an ordinary paragraph
  assert.strictEqual(sanitise('<p class="embed">just text</p>'), "<p>just text</p>");
  assert.strictEqual(sanitise('<p class="embed"><strong>x</strong><a href="https://vimeo.com/1">y</a></p>'), '<p><strong>x</strong><a href="https://vimeo.com/1">y</a></p>');
  assert.strictEqual(sanitise('<p class="file"><a href="/media/2026/10/a.pdf">A</a> (PDF)</p>'), '<p class="file"><a href="/media/2026/10/a.pdf">A</a> (PDF)</p>');
  assert.strictEqual(sanitise('<p class="other"><a href="https://a.org/">x</a></p>'), '<p><a href="https://a.org/">x</a></p>');
  assert.strictEqual(slugify("Pilgrimage to Lourdes – Octobre 2026!"), "pilgrimage-to-lourdes-octobre-2026");
  assert.strictEqual(slugify("Ordine di Malta: più aiuti"), "ordine-di-malta-piu-aiuti");
  assert.strictEqual(slugify("???"), "news");
  assert.strictEqual(stemOf("l-ordre-%C3%A9tait-ici"), "l-ordre--tait-ici");
  assert.strictEqual(canonicalVideo("https://youtu.be/dQw4w9WgXcQ?t=3"), "https://www.youtube.com/watch?v=dQw4w9WgXcQ");
  assert.strictEqual(canonicalVideo("https://m.youtube.com/watch?v=dQw4w9WgXcQ&list=x"), "https://www.youtube.com/watch?v=dQw4w9WgXcQ");
  assert.strictEqual(canonicalVideo("https://vimeo.com/123456"), "https://vimeo.com/123456");
  assert.strictEqual(canonicalVideo(""), "");
  for (const v of ["https://evil.example/watch?v=dQw4w9WgXcQ", "javascript:alert(1)", "https://vimeo.com/abc", "https://www.youtube.com/embed/dQw4w9WgXcQ", "nonsense"]) assert.strictEqual(canonicalVideo(v), null, v);
  assert.deepStrictEqual(users(), { Anna: { password: "secret-pass-1", role: "admin" }, Piero: { password: "other-pass-2", role: "editor" }, Otto: { password: "third:pass", role: "editor" } });
  assert.deepStrictEqual(parsePath("content/news/it/2026/a-b.html"), { type: "news", lang: "it" });
  assert.deepStrictEqual(parsePath("content/galleries/es/2025/x.html"), { type: "gallery", lang: "es" });
  assert.deepStrictEqual(parsePath("content/press/de/2025/x.html"), { type: "press", lang: "de" });
  for (const p of ["content/news/en/2026/../../../.env", "content/pages/en/index.html", "content/news/xx/2026/a.html", "content/news/en/2026/A.html", "content/news/en/26/a.html",
    "content/news/en/2026/a.html/..", "content/news/en/2026/a/b.html", "static/media/2026/10/a.png", "content/news/2026/11/02/a.html", "/content/news/en/2026/a.html", "content/news/en/2026/a.html\n", "content/events.json", "content/news/en/2026/.html", ""]) {
    assert.strictEqual(parsePath(p), null, JSON.stringify(p));
  }

  // ---- sign-in and the info
  const info = await call("GET", null);
  assert.strictEqual(info.body.user, null);
  assert.strictEqual(info.body.features.pin, false);  // nobody signed in: no pinning
  assert.deepStrictEqual(info.body.languages, ["en", "it", "fr", "de", "es"]);
  assert.deepStrictEqual(info.body.types, ["news", "press", "gallery"]);
  assert.strictEqual(info.body.defaultCategory, "all-news");
  assert.ok(info.body.categories["all-news"].en && info.body.categories["all-news"].it);
  assert.strictEqual(info.body.bases.news.it, "/it/notizie/");
  assert.strictEqual(info.body.features.events, undefined);
  assert.strictEqual((await call("POST", { action: "login", name: "Anna", password: "wrong" })).status, 401);
  for (const a of ["upload", "publish", "load", "delete", "events", "event"]) assert.strictEqual((await call("POST", { action: a, path: "content/news/en/2026/x.html" })).status, 401, a);  // no write endpoint works without a session
  const admin = await call("POST", { action: "login", name: "anna", password: "secret-pass-1" });
  assert.strictEqual(admin.status, 200);
  assert.strictEqual(admin.body.role, "admin");
  assert.match(admin.cookie, /HttpOnly; Secure; SameSite=Strict/);
  const A = admin.cookie.split(";")[0];
  const editor = await call("POST", { action: "login", name: "Piero", password: "other-pass-2" });
  assert.strictEqual(editor.body.role, "editor");
  const E = editor.cookie.split(";")[0];
  const other = await call("POST", { action: "login", name: "Otto", password: "third:pass" });
  const O = other.cookie.split(";")[0];
  assert.strictEqual((await call("GET", null, E)).body.features.pin, false);  // an editor is not offered pinning
  assert.strictEqual((await call("GET", null, A)).body.features.pin, true);
  assert.strictEqual((await call("POST", post(), "news_session=Anna|9999999999999|forged")).status, 401);
  assert.strictEqual((await call("POST", post(), "news_session=" + encodeURIComponent("Anna|1|" + "x"))).status, 401);

  // ---- uploads: the content must be what it claims
  const up = await call("POST", { action: "upload", name: "My photo.png", type: "image/png", data: png }, E);
  assert.strictEqual(up.status, 200);
  assert.match(up.body.path, /^static\/media\/\d{4}\/\d{2}\/my-photo-[0-9a-f]{8}\.png$/);
  assert.strictEqual(up.body.url, up.body.path.replace(/^static/, ""));
  assert.strictEqual((await call("POST", { action: "upload", name: "x.pdf", type: "application/pdf", data: png }, E)).status, 400);
  assert.strictEqual((await call("POST", { action: "upload", name: "x.exe", type: "application/octet-stream", data: png }, E)).status, 400);
  assert.strictEqual((await call("POST", { action: "upload", name: "x.png", type: "image/png", data: Buffer.from("<svg onload=x>").toString("base64") }, E)).status, 400);
  assert.strictEqual((await call("POST", { action: "upload", name: "../../x.png", type: "image/png", data: png }, E)).body.path.includes(".."), false);
  assert.strictEqual((await call("POST", { action: "upload", name: "big.png", type: "image/png", data: Buffer.alloc(3 * 1024 * 1024 + 1, 1).toString("base64") }, E)).status, 413);
  const pdf = Buffer.concat([Buffer.from("%PDF-1.7\n"), Buffer.alloc(20)]).toString("base64");
  assert.strictEqual((await call("POST", { action: "upload", name: "Program.pdf", type: "application/pdf", data: pdf }, E)).status, 200);
  const fakeWebp = Buffer.concat([Buffer.from("RIFF"), Buffer.alloc(4), Buffer.from("XXXX")]).toString("base64");
  assert.strictEqual((await call("POST", { action: "upload", name: "a.webp", type: "image/webp", data: fakeWebp }, E)).status, 400);

  // ---- a new news item in English, with every extra field
  const attach = { sha: "b".repeat(40), path: "static/media/2026/10/program-1a2b3c4d.pdf", role: "attachment", label: "Program <PDF>", ext: "pdf" };
  const gal = [{ sha: "e".repeat(40), path: "static/media/2026/11/photo-one-1a2b3c4d.webp", w: 1280, h: 853, alt: "One", caption: "First" }, { src: "/media/2026/10/two.webp", w: 800, h: 600 }];
  const pub = await call("POST", post({ title: "Grand Master visits Rome", subtitle: " A short visit ", categories: [CAT, "bogus", "../x"],
    body: '<p>Welcome <b>all</b>.</p><p><img src="blob:x"><img src="/media/2026/10/a-1.webp"></p><script>x</script><p class="embed"><a href="https://youtu.be/dQw4w9WgXcQ">Clip</a></p>',
    excerpt: "  In short  ", video: "https://youtu.be/dQw4w9WgXcQ", gallery: gal, pinned: true, imageAlt: "Alt text",
    files: [{ sha: up.body.sha, path: up.body.path, url: up.body.url, role: "image" }, attach] }), E);
  assert.strictEqual(pub.status, 200, JSON.stringify(pub.body));
  assert.strictEqual(pub.body.url, "/news/grand-master-visits-rome/");
  assert.strictEqual(pub.body.path, "content/news/en/2026/grand-master-visits-rome.html");
  let tree = lastCommit();
  const doc = fileOf(tree, pub.body.path);
  let m = meta(doc);
  assert.deepStrictEqual(Object.keys(m).slice(0, 5), ["type", "lang", "url", "title", "translations"]);
  assert.deepStrictEqual({ type: m.type, lang: m.lang, url: m.url, translations: m.translations, imported: m.imported, author: m.author },
    { type: "news", lang: "en", url: "/news/grand-master-visits-rome/", translations: { en: "/news/grand-master-visits-rome/" }, imported: false, author: "Piero" });
  assert.deepStrictEqual(m.categories, [CAT]);
  assert.strictEqual(m.subtitle, "A short visit");
  assert.strictEqual(m.video, "https://www.youtube.com/watch?v=dQw4w9WgXcQ");
  assert.strictEqual(m.pinned, undefined);  // an editor cannot pin
  assert.strictEqual(m.draft, undefined);
  assert.strictEqual(m.image, up.body.url);
  assert.strictEqual(m.imageAlt, "Alt text");
  assert.strictEqual(m.excerpt, "In short");
  assert.strictEqual(m.date, "2026-11-02T10:30");
  assert.deepStrictEqual(m.gallery, [{ src: "/media/2026/11/photo-one-1a2b3c4d.webp", w: 1280, h: 853, alt: "One", caption: "First" }, { src: "/media/2026/10/two.webp", w: 800, h: 600, alt: "", caption: "" }]);
  assert.strictEqual(m.kind, undefined);
  assert.strictEqual(m.organisation, undefined);
  assert.match(doc, /<p>Welcome <strong>all<\/strong>\.<\/p>\n<p><img src="\/media\/2026\/10\/a-1\.webp" alt=""><\/p>\n<p class="embed"><a href="https:\/\/youtu\.be\/dQw4w9WgXcQ">Clip<\/a><\/p>\n<p class="file"><a href="\/media\/2026\/10\/program-1a2b3c4d\.pdf">Program &lt;PDF&gt;<\/a> \(PDF\)<\/p>/);
  assert.ok(tree.some((f) => f.path === up.body.path && f.sha === up.body.sha));
  assert.ok(tree.some((f) => f.path === gal[0].path && f.sha === gal[0].sha));
  assert.ok(tree.every((f) => /^content\/(news|press|galleries)\/(en|it|fr|de|es)\/\d{4}\/[a-z0-9-]+\.html$/.test(f.path) || /^static\/media\/\d{4}\/\d{2}\/[a-z0-9-]+\.(pdf|jpg|png|webp)$/.test(f.path)));
  assert.match(commits.messages.at(-1), /^Add news: Grand Master visits Rome \(Piero\)$/);

  // wrong input
  const bad = (extra, status = 400) => call("POST", post(extra), E).then((r) => assert.strictEqual(r.status, status, JSON.stringify(extra) + JSON.stringify(r.body)) || r);
  await bad({ files: [{ url: "https://evil.example/x.png", role: "image" }] });
  await bad({ files: [{ sha: "zz", path: "../../etc/passwd", role: "image" }] });
  await bad({ files: [{ sha: "b".repeat(40), path: "content/news/en/2026/x.html", role: "attachment" }] });  // not a media path
  await bad({ files: [{ sha: "b".repeat(40), path: "static/media/2026/10/../../../api/news.js", role: "attachment" }] });
  await bad({ files: [{ url: "/media/../api/news.js", role: "attachment" }] });
  await bad({ files: [{ url: "/media/2026/10/a.png", role: "weird" }] });
  await bad({ date: "2026-11-02" });  // date without time
  await bad({ date: "2026-13-45T10:00" });
  await bad({ title: "   " });
  await bad({ body: "<script>x</script>" });
  await bad({ lang: "xx" });
  await bad({ lang: "../it" });
  await bad({ type: "event" });
  await bad({ type: "../news" });
  await bad({ video: "https://evil.example/v" });
  await bad({ gallery: [{ src: "https://evil.example/a.webp", w: 1, h: 1 }] });
  await bad({ gallery: [{ src: "/media/a.webp", w: 0, h: 1 }] });
  await bad({ gallery: [{ sha: "e".repeat(40), path: "static/media/2026/11/a.pdf", w: 1, h: 1 }] });  // a gallery holds photos only
  await bad({ gallery: "nope" });
  await bad({ kind: "slideshow" });
  assert.strictEqual((await call("POST", post({ path: "content/news/en/2026/../../../.env" }), E)).status, 400);

  // ---- addresses stay unique across year folders; reserved slugs
  seed("content/news/en/2025/taken-title.html", { type: "news", lang: "en", url: "/news/taken-title/", title: "Taken title", date: "2025-12-01T10:00", categories: ["all-news"], imported: true });
  const t1 = await call("POST", post({ title: "Taken title" }), E);
  assert.strictEqual(t1.body.url, "/news/taken-title-2/");
  assert.strictEqual(t1.body.path, "content/news/en/2026/taken-title-2.html");
  assert.strictEqual((await call("POST", post({ title: "2026" }), E)).body.url, "/news/2026-post/");  // /news/2026/ is the year archive
  assert.strictEqual((await call("POST", post({ title: "Page" }), E)).body.url, "/news/page-post/");

  // ---- the same title in each language gets that language's section
  const urls = { en: "/news/", it: "/it/notizie/", fr: "/fr/actualites/", de: "/de/nachrichten/", es: "/es/noticias/" };
  for (const [lang, base] of Object.entries(urls)) {
    const r = await call("POST", post({ title: "Peace", lang }), E);
    assert.strictEqual(r.body.url, `${base}peace/`, lang);
    assert.strictEqual(r.body.path, `content/news/${lang}/2026/peace.html`);
    assert.strictEqual(meta(fileOf(lastCommit(), r.body.path)).lang, lang);
  }
  const noLang = await call("POST", { ...post({ title: "Default lang" }), lang: undefined, type: undefined }, E);
  assert.strictEqual(noLang.body.path, "content/news/en/2026/default-lang.html");

  // ---- press releases and galleries
  const pr = await call("POST", post({ type: "press", lang: "fr", title: "Communiqué de presse", organisation: " ORDRE DE MALTE ", categories: [CAT], subtitle: "ignored" }), E);
  assert.strictEqual(pr.body.url, "/fr/communiques-de-presse/communique-de-presse/");
  assert.strictEqual(pr.body.path, "content/press/fr/2026/communique-de-presse.html");
  m = meta(fileOf(lastCommit(), pr.body.path));
  assert.strictEqual(m.type, "press");
  assert.strictEqual(m.organisation, "ORDRE DE MALTE");
  assert.strictEqual(m.categories, undefined);  // categories belong to news
  assert.strictEqual(m.subtitle, undefined);
  assert.match(commits.messages.at(-1), /^Add press release:/);
  const ga = await call("POST", post({ type: "gallery", lang: "de", title: "Fotos der Wallfahrt", body: "", gallery: gal, kind: "album" }), E);
  assert.strictEqual(ga.status, 200, JSON.stringify(ga.body));
  assert.strictEqual(ga.body.url, "/de/foto-und-videogalerien/fotos-der-wallfahrt/");
  assert.strictEqual(ga.body.path, "content/galleries/de/2026/fotos-der-wallfahrt.html");
  m = meta(fileOf(lastCommit(), ga.body.path));
  assert.deepStrictEqual({ type: m.type, kind: m.kind, n: m.gallery.length }, { type: "gallery", kind: "album", n: 2 });
  const gv = await call("POST", post({ type: "gallery", lang: "es", title: "Vídeo del Gran Maestre", body: "", video: "https://vimeo.com/123456" }), E);
  assert.strictEqual(gv.status, 200);
  m = meta(fileOf(lastCommit(), gv.body.path));
  assert.deepStrictEqual({ kind: m.kind, video: m.video }, { kind: "video", video: "https://vimeo.com/123456" });
  assert.strictEqual((await call("POST", post({ type: "gallery", title: "Empty", body: "" }), E)).status, 400);  // no text, photos or video
  assert.strictEqual((await call("POST", post({ type: "news", title: "Empty news", body: "", video: "https://vimeo.com/1" }), E)).status, 400);

  // ---- translations: a group of posts in different languages
  const enPath = "content/news/en/2026/grand-master-visits-rome.html";
  const it = await call("POST", post({ lang: "it", title: "Il Gran Maestro a Roma", translationOf: enPath }), E);
  assert.strictEqual(it.status, 200, JSON.stringify(it.body));
  tree = lastCommit();
  const itMeta = meta(fileOf(tree, it.body.path));
  const group2 = { en: "/news/grand-master-visits-rome/", it: "/it/notizie/il-gran-maestro-a-roma/" };
  assert.deepStrictEqual(itMeta.translations, group2);
  assert.deepStrictEqual(meta(fileOf(tree, enPath)).translations, group2);  // the other member is rewritten in the same commit
  assert.match(fileOf(tree, enPath), /<p>Welcome <strong>all<\/strong>\.<\/p>/);  // its text is untouched
  assert.strictEqual(meta(fileOf(tree, enPath)).author, "Piero");
  const fr = await call("POST", post({ lang: "fr", title: "Le Grand Maître à Rome", translationOf: it.body.path }), A);  // link to a member that is not the first
  assert.strictEqual(fr.status, 200, JSON.stringify(fr.body));
  tree = lastCommit();
  const group3 = { en: group2.en, it: group2.it, fr: "/fr/actualites/le-grand-maitre-a-rome/" };
  for (const p of [enPath, it.body.path, fr.body.path]) assert.deepStrictEqual(meta(fileOf(tree, p)).translations, group3, p);
  assert.deepStrictEqual(Object.keys(meta(fileOf(tree, fr.body.path)).translations), ["en", "it", "fr"]);  // site language order
  assert.deepStrictEqual(fr.body.unlinked, []);
  // a language that already has a post in the group cannot get a second one
  const dup = await call("POST", post({ lang: "it", title: "Un altro", translationOf: fr.body.path }), E);
  assert.strictEqual(dup.status, 409);
  assert.strictEqual((await call("POST", post({ lang: "fr", title: "Same language", translationOf: enPath.replace("/en/", "/fr/") }), E)).status, 400);
  assert.strictEqual((await call("POST", post({ lang: "en", title: "Same language", translationOf: enPath }), E)).status, 400);  // not another language
  assert.strictEqual((await call("POST", post({ lang: "de", title: "Wrong type", translationOf: pr.body.path }), E)).status, 400);  // a news item is not the translation of a press release
  for (const t of ["content/pages/en/index.html", "../../etc/passwd", "content/news/en/2026/x.html/../../../.env", "static/media/2026/10/a.png"]) {
    assert.strictEqual((await call("POST", post({ lang: "de", title: "Bad link", translationOf: t }), E)).status, 400, t);
  }
  assert.strictEqual((await call("POST", post({ lang: "de", title: "Missing target", translationOf: "content/news/en/2026/nothing-here.html" }), E)).status, 404);
  // linking an existing post (edit) to a group
  const de = await call("POST", post({ lang: "de", title: "Der Großmeister in Rom" }), E);
  assert.deepStrictEqual(meta(fileOf(lastCommit(), de.body.path)).translations, { de: "/de/nachrichten/der-grossmeister-in-rom/" });
  const link = await call("POST", { ...post({ title: "Der Großmeister in Rom", translationOf: enPath }), path: de.body.path }, E);
  assert.strictEqual(link.status, 200, JSON.stringify(link.body));
  tree = lastCommit();
  for (const p of [enPath, it.body.path, fr.body.path, de.body.path]) assert.strictEqual(Object.keys(meta(fileOf(tree, p)).translations).length, 4, p);
  assert.strictEqual(link.body.url, de.body.url);  // the address never changes
  // deleting a member removes it from the others
  const rm = await call("POST", { action: "delete", path: de.body.path }, E);
  assert.strictEqual(rm.status, 200);
  tree = lastCommit();
  assert.ok(tree.some((f) => f.path === de.body.path && f.sha === null));
  assert.deepStrictEqual(Object.keys(meta(fileOf(tree, enPath)).translations), ["en", "it", "fr"]);

  // ---- a draft and a scheduled post
  const draft = await call("POST", post({ title: "Unfinished", draft: true }), E);
  assert.strictEqual(draft.body.draft, true);
  assert.strictEqual(meta(fileOf(lastCommit(), draft.body.path)).draft, true);
  assert.match(commits.messages.at(-1), /^Draft news:/);
  const future = await call("POST", post({ title: "Next century", date: "2099-01-01T08:00" }), E);
  assert.strictEqual(future.body.scheduled, true);
  assert.strictEqual(meta(fileOf(lastCommit(), future.body.path)).draft, undefined);
  assert.match(commits.messages.at(-1), /^Schedule news:/);

  // ---- editing: an editor only their own, an admin anything; the admin can pin
  const path = pub.body.path;
  const loaded = await call("POST", { action: "load", path }, A);
  assert.strictEqual(loaded.status, 200);
  assert.deepStrictEqual({ type: loaded.body.type, lang: loaded.body.lang, mayChange: loaded.body.mayChange, pinned: loaded.body.pinned, subtitle: loaded.body.subtitle, video: loaded.body.video },
    { type: "news", lang: "en", mayChange: true, pinned: false, subtitle: "A short visit", video: "https://www.youtube.com/watch?v=dQw4w9WgXcQ" });
  assert.strictEqual(loaded.body.gallery.length, 2);
  assert.strictEqual(loaded.body.attachments[0].label, "Program &lt;PDF&gt;");
  assert.deepStrictEqual(Object.keys(loaded.body.translations), ["en", "it", "fr"]);
  assert.strictEqual((await call("POST", { action: "load", path }, O)).body.mayChange, false);
  assert.strictEqual((await call("POST", { ...post({ title: "Stolen" }), path }, O)).status, 403);
  assert.strictEqual((await call("POST", { action: "delete", path }, O)).status, 403);
  const pinned = await call("POST", { ...post({ title: "Grand Master visits Rome (pinned)", categories: [CAT], files: [{ url: up.body.url, role: "image" }], pinned: true }), path }, A);
  assert.strictEqual(pinned.status, 200);
  assert.strictEqual(pinned.body.url, "/news/grand-master-visits-rome/");  // the address never changes
  let pm = meta(fileOf(lastCommit(), path));
  assert.strictEqual(pm.pinned, true);
  assert.strictEqual(pm.author, "Piero");  // the author stays
  assert.strictEqual(pm.editedBy, "Anna");
  assert.strictEqual(pm.imageAlt, "Alt text");  // unchanged image keeps its alt text
  assert.deepStrictEqual(pm.translations, group3);  // editing keeps the translation group
  assert.ok(!lastCommit().some((f) => f.path !== path && !f.path.startsWith("static/")));  // and does not touch the others
  await call("POST", { ...post({ title: "Grand Master visits Rome (edited)", categories: [CAT], pinned: false }), path }, E);  // the editor's later save keeps the admin's pin
  pm = meta(fileOf(lastCommit(), path));
  assert.strictEqual(pm.pinned, true);
  assert.strictEqual(pm.title, "Grand Master visits Rome (edited)");
  assert.strictEqual(pm.url, "/news/grand-master-visits-rome/");
  // an imported post (no author) stays editable by any editor, and loses its "unreviewed" status when saved
  seed("content/news/it/2025/vecchio.html", { type: "news", lang: "it", url: "/it/notizie/vecchio/", title: "Vecchio", date: "2025-09-14T10:00", categories: ["all-news"], image: "/media/2025/06/old.webp", excerpt: "Vecchio", status: "existing", imported: true, id: 77, source: "https://www.orderofmalta.int/it/notizie/vecchio/" },
    '<p>Vecchio testo.</p>\n<figure class="media"><img src="/media/2025/06/old.webp"><figcaption>Didascalia</figcaption></figure>\n');
  const old = await call("POST", { action: "load", path: "content/news/it/2025/vecchio.html" }, O);
  assert.strictEqual(old.body.editable, false);
  assert.strictEqual(old.body.mayChange, true);
  await call("POST", { ...post({ title: "Vecchio (corretto)", date: "2025-09-14T10:00", body: "", categories: [CAT], files: [{ url: "/media/2025/06/old.webp", role: "image" }] }), path: "content/news/it/2025/vecchio.html" }, O);
  const om = meta(fileOf(lastCommit(), "content/news/it/2025/vecchio.html"));
  assert.deepStrictEqual({ status: om.status, editedBy: om.editedBy, imported: om.imported, id: om.id, url: om.url, lang: om.lang }, { status: undefined, editedBy: "Otto", imported: false, id: 77, url: "/it/notizie/vecchio/", lang: "it" });
  assert.match(fileOf(lastCommit(), "content/news/it/2025/vecchio.html"), /<figcaption>Didascalia<\/figcaption>/);  // the old text is kept as it was

  // ---- deleting: the author or an admin
  assert.strictEqual((await call("POST", { action: "delete", path: "../../.env" }, A)).status, 400);
  assert.strictEqual((await call("POST", { action: "delete", path: "content/pages/en/index.html" }, A)).status, 400);
  assert.strictEqual((await call("POST", { action: "load", path: "content/events.json" }, A)).status, 400);
  assert.strictEqual((await call("POST", { action: "delete", path: "content/news/en/2026/nothing.html" }, A)).status, 404);
  assert.strictEqual((await call("POST", { action: "events" }, A)).status, 400);  // the events feature is gone
  const del = await call("POST", { action: "delete", path: draft.body.path }, E);
  assert.strictEqual(del.status, 200);
  assert.deepStrictEqual(lastCommit(), [{ path: draft.body.path, mode: "100644", type: "blob", sha: null }]);

  // ---- every file ever committed is on one of the allowed paths
  for (const tr of commits) for (const f of tr) {
    assert.ok(/^content\/(news|press|galleries)\/(en|it|fr|de|es)\/\d{4}\/[a-z0-9-]+\.html$/.test(f.path) || /^static\/media\/\d{4}\/\d{2}\/[a-z0-9-]+\.(pdf|jpg|png|webp)$/.test(f.path), f.path);
  }

  // ---- notifications go only through the configured sender
  const mails = [];
  const realFetch = global.fetch;
  global.fetch = async (url, opts) => { if (String(url).startsWith("https://api.resend.com")) { mails.push(JSON.parse(opts.body)); return { ok: true, status: 200, json: async () => ({}) }; } return realFetch(url, opts); };
  process.env.RESEND_API_KEY = "re_test"; process.env.NEWS_NOTIFY = "desk@example.test";
  await call("POST", post({ title: "No sender" }), E);
  assert.strictEqual(mails.length, 0);  // MAIL_FROM unset: no mail, no invented address
  process.env.MAIL_FROM = "web@example.test";
  await call("POST", post({ title: "With sender <b>" }), E);
  assert.strictEqual(mails.length, 1);
  assert.strictEqual(mails[0].from, "web@example.test");
  assert.match(mails[0].subject, /^New news: /);
  assert.ok(mails[0].html.includes("With sender &lt;b&gt;") && !mails[0].html.includes("sender <b>"));
  global.fetch = realFetch;

  // ---- no cross-site posts, no publishing without configuration
  const evil = await new Promise((done) => handler({ method: "POST", headers: { host: HOST, origin: "https://evil.example" }, body: {} },
    { statusCode: 200, setHeader() {}, end(s) { done({ status: this.statusCode, body: JSON.parse(s) }); } }));
  assert.strictEqual(evil.status, 403);
  assert.strictEqual((await call("POST", {}, null, { origin: "not a url" })).status, 403);
  process.env.GITHUB_TOKEN = "";
  assert.strictEqual((await call("POST", { action: "login", name: "Anna", password: "secret-pass-1" })).status, 503);
  console.log("news ok");
})().catch((e) => { console.error(e); process.exit(1); });
