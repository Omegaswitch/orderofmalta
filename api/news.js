// Staff publishing for the Sovereign Order of Malta site (the page at /editor/): staff sign in, upload files one by one
// (each request stays under Vercel's 4.5 MB body limit) and publish. A post is committed to the main branch as
//   content/news/<lang>/<YYYY>/<slug>.html        (news)
//   content/press/<lang>/<YYYY>/<slug>.html       (press releases)
//   content/galleries/<lang>/<YYYY>/<slug>.html   (photo and video galleries)
// and its photos and documents to static/media/<YYYY>/<MM>/. Nothing else can be written. Vercel then rebuilds the site.
// Five languages (en, it, fr, de, es); a post can be linked to its translations (the "translations" map in the front
// matter of every member of the group is kept in step, in the same commit).
//
// Sign-in: Better Auth (api/_auth.mjs) when DATABASE_URL is set; otherwise the older NEWS_USERS list below (tests and
// the local stand-in only).
// Env: DATABASE_URL, BETTER_AUTH_SECRET, BETTER_AUTH_URL      Better Auth (see api/_auth.mjs)
//      NEWS_USERS   one "Name:password" or "Name:password:admin" per line (or separated by ";"); legacy, no database needed
//      NEWS_SECRET  long random string that signs the legacy sign-in cookie
//      GITHUB_TOKEN fine-grained token, this repository only, Contents: read and write
//      GITHUB_REPO  owner/name (default below), GITHUB_BRANCH (default main)
//      optional: RESEND_API_KEY, NEWS_NOTIFY (who is emailed about each change), MAIL_FROM (sender; no mail without it),
//                COMMIT_EMAIL (author e-mail of the commits; default is built from the site's domain)
const crypto = require("crypto");

const DEFAULT_REPO = "Omegaswitch/orderofmalta";
const FEATURES = { pin: true };  // pin: a notice pinned to the home page and the news list of its language

// ---------------------------------------------------------------- site configuration
// content/site.json is written by the build; the same values are the fallback until it has them.
let SITE = {};
try { SITE = require("../content/site.json"); } catch { SITE = {}; }
let CATEGORY_FILE = {};
try { CATEGORY_FILE = require("../content/translations/categories.json"); } catch { CATEGORY_FILE = {}; }

const FALLBACK_SECTIONS = {
  news: { en: "/news/", it: "/it/notizie/", fr: "/fr/actualites/", de: "/de/nachrichten/", es: "/es/noticias/" },
  press: { en: "/press-releases/", it: "/it/comunicati-stampa/", fr: "/fr/communiques-de-presse/", de: "/de/pressemitteilungen/", es: "/es/comunicados-de-prensa/" },
  galleries: { en: "/photo-and-video-galleries/", it: "/it/gallerie-foto-e-video/", fr: "/fr/galeries-photo-et-video/", de: "/de/foto-und-videogalerien/", es: "/es/galerias-de-fotos-y-videos/" },
};
const BASE_URL = String(SITE.baseUrl || "https://www.orderofmalta.int").replace(/\/+$/, "");
const TIME_ZONE = SITE.timezone || "Europe/Rome";
const LANGS = (Array.isArray(SITE.languages) && SITE.languages.length ? SITE.languages : ["en", "it", "fr", "de", "es"]).filter((l) => /^[a-z]{2}$/.test(l));
const TYPES_LIST = ["news", "press", "gallery"];
const DIR = { news: "news", press: "press", gallery: "galleries" };  // type -> folder under content/
const TYPE_OF_DIR = { news: "news", press: "press", galleries: "gallery" };
const BASES = {};
for (const t of TYPES_LIST) {
  const key = DIR[t], own = (SITE.sections && SITE.sections[key]) || {};
  BASES[t] = {};
  for (const l of LANGS) BASES[t][l] = own[l] || FALLBACK_SECTIONS[key][l];
}
const DOMAIN = new URL(BASE_URL).host.replace(/^www\./, "");

const CATEGORIES = Object.keys(CATEGORY_FILE).length ? CATEGORY_FILE : { "all-news": { parent: null, terms: {} } };
const DEFAULT_CATEGORY = "all-news" in CATEGORIES ? "all-news" : Object.keys(CATEGORIES)[0];
const categoryLabels = () => Object.fromEntries(Object.keys(CATEGORIES).map((k) => [k,
  Object.fromEntries(LANGS.map((l) => [l, ((CATEGORIES[k].terms || {})[l] || {}).name || ((CATEGORIES[k].terms || {}).en || {}).name || k]))]));

// ---------------------------------------------------------------- limits and patterns
const COOKIE = "news_session";
const SESSION_HOURS = 12;
const MAX_FILE = 3 * 1024 * 1024; // after the browser has shrunk photos; base64 in JSON keeps the request under 4.5 MB
const MAX_TEXT = 200000;
const MAX_GALLERY = 100;
const UPLOAD_TYPES = { "application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp" };
const MAGIC = [[[0x25, 0x50, 0x44, 0x46], "application/pdf"], [[0xff, 0xd8, 0xff], "image/jpeg"],
  [[0x89, 0x50, 0x4e, 0x47], "image/png"], [[0x52, 0x49, 0x46, 0x46], "image/webp"]];
const KINDS = ["photo", "album", "video"];

const LANG_RE = LANGS.join("|");
// the only places the API may write to
const POST_PATH = new RegExp(`^content/(news|press|galleries)/(${LANG_RE})/\\d{4}/[a-z0-9-]{1,120}\\.html$`);
const MEDIA_FILE = /^static\/media\/\d{4}\/\d{2}\/[a-z0-9-]{1,80}\.(pdf|jpg|png|webp)$/;
const MEDIA_IMAGE = /^static\/media\/\d{4}\/\d{2}\/[a-z0-9-]{1,80}\.(jpg|png|webp)$/;
const MEDIA_URL = /^\/media\/(?!.*\.\.)[A-Za-z0-9\/._%-]+$/;
const DATE_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/;
const FILE_P = /\n?<p class="file"><a href="([^"]+)">([^<]*)<\/a> \(([A-Z0-9]+)\)<\/p>/g;
const RESERVED_SLUG = /^(\d{4}|page|feed)$/;  // a year archive, the pager and the feed own these addresses
const YT_ID = "[A-Za-z0-9_-]{6,20}";
const EMBED_URL = [new RegExp(`^https://www\\.youtube\\.com/watch\\?v=${YT_ID}(&[A-Za-z0-9_=%.&-]*)?$`),
  new RegExp(`^https://youtu\\.be/${YT_ID}(\\?[A-Za-z0-9_=%.&-]*)?$`), /^https:\/\/vimeo\.com\/\d{1,12}$/];

const writable = (p) => POST_PATH.test(p) || MEDIA_FILE.test(p);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const env = (k, d = "") => process.env[k] || d;

// ---------------------------------------------------------------- sign-in and roles

function users() {
  const out = {};
  for (const line of env("NEWS_USERS").split(/[\n;]/)) {
    const i = line.indexOf(":");
    if (i <= 0) continue;
    let password = line.slice(i + 1).trim(), role = "editor";
    const m = password.match(/^(.*):(editor|admin)$/);
    if (m) { password = m[1]; role = m[2]; }
    if (password) out[line.slice(0, i).trim()] = { password, role };
  }
  return out;
}
const authRoles = {}, owners = {};  // name -> role of people signed in through Better Auth
const roleOf = (name) => authRoles[name] || (users()[name] || {}).role || "editor";
const betterAuth = () => !!env("DATABASE_URL");

const same = (a, b) => {
  const x = crypto.createHash("sha256").update(String(a)).digest(), y = crypto.createHash("sha256").update(String(b)).digest();
  return crypto.timingSafeEqual(x, y);
};
const sign = (v) => crypto.createHmac("sha256", env("NEWS_SECRET")).update(v).digest("base64url");

async function session(req) {
  if (betterAuth()) {
    const { auth } = await import("./_auth.mjs");
    const s = await auth.api.getSession({ headers: new Headers(Object.entries(req.headers).map(([k, v]) => [k, String(v)])) });
    if (!s || s.user.banned) return null;
    authRoles[s.user.name] = s.user.role === "admin" || s.user.role === "owner" ? "admin" : "editor";
    owners[s.user.name] = s.user.role === "owner";
    return s.user.name;
  }
  const m = (req.headers.cookie || "").match(new RegExp(`(?:^|;\\s*)${COOKIE}=([^;]+)`));
  if (!m || !env("NEWS_SECRET")) return null;
  const [name, exp, mac] = decodeURIComponent(m[1]).split("|");
  if (!name || !mac || !same(mac, sign(`${name}|${exp}`)) || Date.now() > Number(exp)) return null;
  return name in users() ? name : null;  // removing someone from NEWS_USERS signs them out
}

function setCookie(res, value, maxAge) {
  res.setHeader("Set-Cookie", `${COOKIE}=${encodeURIComponent(value)}; Path=/api/news; HttpOnly; Secure; SameSite=Strict; Max-Age=${maxAge}`);
}

const failures = new Map(); // per instance: a few wrong passwords slow the next attempt down
async function throttle(ip) {
  const n = failures.get(ip) || 0;
  if (n) await new Promise((r) => setTimeout(r, Math.min(8000, 500 * 2 ** n)));
}

// An editor may change what they wrote (or what nobody signed: imported posts); an admin may change anything.
const mayChange = (user, meta) => roleOf(user) === "admin" || !meta.author || meta.author === user || meta.editedBy === user;

// ---------------------------------------------------------------- text

const ALLOWED = new Set(["p", "br", "h2", "h3", "strong", "em", "u", "s", "a", "ul", "ol", "li", "blockquote", "img"]);
const RENAME = { b: "strong", i: "em", h1: "h2", h4: "h3", strike: "s", del: "s" };
const VOID = new Set(["br", "img"]);

function safeHref(v) {
  v = v.trim();
  return /^(https?:\/\/|mailto:|\/(?!\/))/i.test(v) ? v : null;
}
const embedUrl = (v) => EMBED_URL.some((r) => r.test(v));
const unentity = (v) => v.replace(/&quot;/g, '"').replace(/&#39;|&apos;/g, "'").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");

// Rebuilds every tag from an allowlist; anything else becomes text or disappears. The editor sends semantic
// HTML (headings, bold, lists, links, quotes, photos uploaded to /media/, video links), so nothing legitimate is lost.
// <p class="embed"><a href> is kept only for YouTube and Vimeo watch links; <p class="file"> for downloads; any other class goes.
function sanitise(html) {
  html = String(html).replace(/<!--[\s\S]*?-->/g, "").replace(/<(script|style|iframe|object|svg|math)\b[\s\S]*?<\/\1\s*>/gi, "")
    .replace(/&nbsp;| /g, " ");
  let out = "";
  const open = [];
  let inEmbed = false;
  for (const part of html.split(/(<\/?[a-zA-Z][^<>]*>)/)) {
    const m = part.match(/^<(\/?)([a-zA-Z][a-zA-Z0-9]*)([^<>]*)>$/);
    if (!m) { out += part.replace(/</g, "&lt;").replace(/>/g, "&gt;"); continue; }
    const closing = !!m[1];
    const name = RENAME[m[2].toLowerCase()] || m[2].toLowerCase();
    if (!ALLOWED.has(name)) continue;
    if (closing) {
      const i = open.lastIndexOf(name);
      if (i < 0) continue;
      while (open.length > i) { const t = open.pop(); out += `</${t}>`; if (t === "p") inEmbed = false; }
      continue;
    }
    const attr = (k) => { const a = m[3].match(new RegExp(`\\s${k}\\s*=\\s*("([^"]*)"|'([^']*)'|([^\\s>]+))`, "i")); return a ? unentity(a[2] ?? a[3] ?? a[4]) : null; };
    let tag = name;
    if (name === "p") {
      const cls = (attr("class") || "").trim();
      if (cls === "embed" || cls === "file") tag += ` class="${cls}"`;
      inEmbed = cls === "embed";
    } else if (name === "a") {
      const href = safeHref(attr("href") || "");
      if (!href || (inEmbed && !embedUrl(href))) continue;
      tag += ` href="${esc(href)}"`;
    } else if (name === "img") {
      const src = attr("src") || "";
      if (!MEDIA_URL.test(src)) continue;  // only photos uploaded through the form
      tag += ` src="${esc(src)}" alt="${esc(attr("alt") || "")}"`;
    }
    out += `<${tag}>`;
    if (!VOID.has(name)) open.push(name);
  }
  while (open.length) out += `</${open.pop()}>`;
  return out.replace(/<(p|h2|h3|li|blockquote|strong|em|u|s)(?: class="(?:embed|file)")?>\s*<\/\1>/g, "").replace(/<p><br><\/p>/g, "")
    // an embed paragraph holds exactly one link (an allowed video host); anything else is an ordinary paragraph
    .replace(/<p class="embed">([\s\S]*?)<\/p>/g, (all, inner) => /^<a href="[^"]+">[^<]*<\/a>$/.test(inner) ? all : `<p>${inner}</p>`)
    .trim();
}

const plain = (html) => html.replace(/<\/?(p|h2|h3|li|ul|ol|blockquote|br)\b[^>]*>/g, " ").replace(/<[^>]+>/g, "").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&").replace(/\s+/g, " ").trim();
const excerptOf = (text) => (text.length <= 180 ? text : text.slice(0, text.lastIndexOf(" ", 180)) + "…");
const oneLine = (s, max) => String(s || "").replace(/\s+/g, " ").trim().slice(0, max);

const TRANSLIT = { "ß": "ss", "æ": "ae", "œ": "oe", "ø": "o", "ł": "l", "đ": "d", "ð": "d", "þ": "th" };
function slugify(s) {
  return s.toLowerCase().replace(/[ßæœøłđðþ]/g, (c) => TRANSLIT[c]).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 70).replace(/-$/, "") || "news";
}

// the file name the importer gives a URL slug (lower-cased, percent-decoded, [a-z0-9-] only, at most 120 characters)
function stemOf(slug) {
  let s = slug;
  try { s = decodeURIComponent(slug); } catch { /* keep as is */ }
  return s.toLowerCase().replace(/[^a-z0-9-]/g, "-").slice(0, 120);
}

function sniff(buf) {
  for (const [sig, type] of MAGIC) if (sig.every((b, i) => buf[i] === b)) return type === "image/webp" && buf.toString("ascii", 8, 12) !== "WEBP" ? null : type;
  return null;
}

// "https://youtu.be/ID", ".../watch?v=ID" or "vimeo.com/123" -> the canonical watch URL; "" when empty; null when not allowed
function canonicalVideo(v) {
  v = String(v || "").trim();
  if (!v) return "";
  let u;
  try { u = new URL(v); } catch { return null; }
  if (u.protocol !== "https:" && u.protocol !== "http:") return null;
  const h = u.hostname.toLowerCase();
  let id;
  if (h === "youtu.be") id = u.pathname.slice(1);
  else if (h === "www.youtube.com" || h === "youtube.com" || h === "m.youtube.com") id = u.pathname === "/watch" ? u.searchParams.get("v") : null;
  else if (h === "vimeo.com" || h === "www.vimeo.com") { const n = u.pathname.match(/^\/(\d{1,12})\/?$/); return n ? `https://vimeo.com/${n[1]}` : null; }
  else return null;
  return id && new RegExp(`^${YT_ID}$`).test(id) ? `https://www.youtube.com/watch?v=${id}` : null;
}

// ---------------------------------------------------------------- time (site time zone)

function parts(date = new Date()) {
  return Object.fromEntries(new Intl.DateTimeFormat("en-GB", { timeZone: TIME_ZONE, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" })
    .formatToParts(date).map((x) => [x.type, x.value]));
}
// "YYYY-MM-DDTHH:MM" in the site's time zone, the same form the editor sends (it fills in the device's local time)
function localNow() {
  const p = parts();
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}
function validDate(d) {
  if (!DATE_RE.test(d || "")) return false;
  const t = new Date(`${d}:00Z`);
  return !isNaN(t) && t.toISOString().slice(0, 16) === d;
}

// ---------------------------------------------------------------- GitHub

async function gh(path, opts = {}) {
  const r = await fetch(`https://api.github.com/repos/${env("GITHUB_REPO", DEFAULT_REPO)}${path}`, {
    ...opts,
    headers: { Authorization: `Bearer ${env("GITHUB_TOKEN")}`, Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "order-of-malta-editor", ...(opts.body ? { "Content-Type": "application/json" } : {}) },
  });
  if (r.status === 404 && opts.allow404) return null;
  if (!r.ok) throw Object.assign(new Error(`GitHub ${r.status} ${path}`), { status: r.status });
  return r.json();
}

const contentsPath = (path) => `/contents/${path.split("/").map(encodeURIComponent).join("/")}?ref=${env("GITHUB_BRANCH", "main")}`;

async function exists(path) {
  return !!(await gh(contentsPath(path), { allow404: true }));
}

async function readFile(path) {
  const r = await gh(contentsPath(path), { allow404: true });
  return r && typeof r.content === "string" ? Buffer.from(r.content, "base64").toString("utf8") : null;
}

async function commit(files, message, author) {
  // files: [{path, content} | {path, sha} | {path, delete}]; one commit on top of the branch, retried once if someone else pushed meanwhile
  if (files.some((f) => !writable(f.path))) throw Object.assign(new Error("refused path"), { status: 400 });  // the API never writes anywhere else
  const branch = env("GITHUB_BRANCH", "main");
  for (let attempt = 0; ; attempt++) {
    const ref = await gh(`/git/ref/heads/${branch}`);
    const head = await gh(`/git/commits/${ref.object.sha}`);
    const tree = await gh("/git/trees", { method: "POST", body: JSON.stringify({ base_tree: head.tree.sha,
      tree: files.map((f) => ({ path: f.path, mode: "100644", type: "blob", ...(f.delete ? { sha: null } : f.sha ? { sha: f.sha } : { content: f.content }) })) }) });
    const c = await gh("/git/commits", { method: "POST", body: JSON.stringify({ message, tree: tree.sha, parents: [ref.object.sha],
      author: { name: author, email: env("COMMIT_EMAIL", `web-editor@${DOMAIN}`) } }) });
    try {
      return await gh(`/git/refs/heads/${branch}`, { method: "PATCH", body: JSON.stringify({ sha: c.sha }) });
    } catch (e) {
      if (attempt || e.status !== 422) throw e;
    }
  }
}

async function notify(subject, html) {
  if (!env("RESEND_API_KEY") || !env("NEWS_NOTIFY") || !env("MAIL_FROM")) return;
  await fetch("https://api.resend.com/emails", {
    method: "POST", headers: { Authorization: `Bearer ${env("RESEND_API_KEY")}`, "Content-Type": "application/json" },
    body: JSON.stringify({ from: env("MAIL_FROM"), to: env("NEWS_NOTIFY").split(/[,;\s]+/).filter(Boolean), subject, html }),
  }).catch(() => {});  // a failed notice never blocks publishing
}

// ---------------------------------------------------------------- files

async function upload(body) {
  const type = UPLOAD_TYPES[body.type] ? body.type : null;
  const buf = Buffer.from(String(body.data || ""), "base64");
  if (!type || !buf.length) return [400, { error: "type" }];
  if (buf.length > MAX_FILE) return [413, { error: "size" }];
  if (sniff(buf) !== type) return [400, { error: "type" }];  // the content must match the declared type
  const p = parts(), y = p.year, m = p.month;
  const stem = slugify(String(body.name || "").replace(/\.[^.]*$/, "")).slice(0, 50);
  const path = `static/media/${y}/${m}/${stem}-${crypto.randomBytes(4).toString("hex")}.${UPLOAD_TYPES[type]}`;  // never the uploader's own name alone
  const blob = await gh("/git/blobs", { method: "POST", body: JSON.stringify({ content: buf.toString("base64"), encoding: "base64" }) });
  return [200, { sha: blob.sha, path, url: path.replace(/^static/, ""), size: buf.length, type }];
}

// ---------------------------------------------------------------- posts

// older imported posts may hold captions, tables, details or layout the editor cannot reproduce; their text is kept as it is
const editable = (html) => !/<(figure|figcaption|table|hr|h4|h5|div|iframe|video|sup|sub|details|summary|section|ul class|ol class)\b|<p class="lead"|<a class="btn"/i.test(html);

function parsePath(path) {
  const m = POST_PATH.exec(String(path || ""));
  if (!m) return null;
  return { type: TYPE_OF_DIR[m[1]], lang: m[2] };
}

// front matter and body of a stored file; the body is returned exactly as stored
function split(text) {
  if (!text || !text.startsWith("---\n")) return null;
  const rest = text.slice(4), i = rest.indexOf("\n---\n");
  if (i < 0) return null;
  try { return { meta: JSON.parse(rest.slice(0, i)), raw: rest.slice(i + 5) }; } catch { return null; }
}
const join = (meta, raw) => `---\n${JSON.stringify(meta, null, 1)}\n---\n${raw}`;

async function readPost(path) {
  const parsed = split(await readFile(path));
  if (!parsed) return null;
  const attachments = [];
  const body = parsed.raw.replace(FILE_P, (_, url, label, ext) => { attachments.push({ url, label, ext }); return ""; }).trim();
  return { meta: parsed.meta, body, raw: parsed.raw, attachments };
}

// where a post with this address is stored: the folder year is the year of its date, which the address does not tell
async function locate(type, lang, url) {
  const base = (BASES[type] || {})[lang];
  if (!base || typeof url !== "string" || !url.startsWith(base) || !url.endsWith("/") || url.length <= base.length) return null;
  const stem = stemOf(url.slice(base.length, -1));
  if (!stem) return null;
  const dir = `content/${DIR[type]}/${lang}`;
  const list = await gh(contentsPath(dir), { allow404: true });
  const years = (Array.isArray(list) ? list : []).filter((e) => e.type === "dir" && /^\d{4}$/.test(e.name)).map((e) => e.name).sort().reverse().slice(0, 40);
  for (const y of years) {
    const p = `${dir}/${y}/${stem}.html`;
    if (POST_PATH.test(p) && await exists(p)) return p;
  }
  return null;
}

async function load(body, user) {
  const pp = parsePath(body.path);
  if (!pp) return [400, { error: "path" }];
  const n = await readPost(body.path);
  if (!n) return [404, { error: "gone" }];
  const m = n.meta;
  return [200, { path: body.path, type: pp.type, lang: pp.lang, title: m.title, subtitle: m.subtitle || "", date: String(m.date || "").slice(0, 16),
    categories: m.categories || [], excerpt: m.excerpt || "", organisation: m.organisation || "", kind: m.kind || "", video: m.video || "",
    gallery: Array.isArray(m.gallery) ? m.gallery : [], translations: m.translations || {}, image: m.image || null, imageAlt: m.imageAlt || "",
    imageCredit: m.imageCredit || "", url: m.url, author: m.author || null, draft: !!m.draft, pinned: !!m.pinned, body: n.body, attachments: n.attachments,
    editable: editable(n.body), mayChange: mayChange(user, m) }];
}

// the members of a translation group other than the post itself, as {lang: path}; unresolved ones are listed apart
async function members(type, lang, translations, selfUrl) {
  const found = {}, missing = [];
  for (const [l, u] of Object.entries(translations || {})) {
    if (!LANGS.includes(l) || u === selfUrl) continue;
    const p = await locate(type, l, u);
    if (p) found[l] = p; else missing.push(u);
  }
  return { found, missing };
}

// rewrites the "translations" map of the given posts (other members of a group) into the commit
async function retarget(paths, map, files) {
  for (const p of Object.values(paths)) {
    const parsed = split(await readFile(p));
    if (!parsed) continue;
    if (JSON.stringify(parsed.meta.translations || {}) === JSON.stringify(map)) continue;
    files.push({ path: p, content: join({ ...parsed.meta, translations: map }, parsed.raw) });
  }
}

// linking a translation rewrites the other members of the group: only members the user may change can be touched
async function mayRetarget(paths, user) {
  for (const p of Object.values(paths)) {
    const parsed = split(await readFile(p));
    if (parsed && !mayChange(user, parsed.meta)) return false;
  }
  return true;
}

async function remove(body, user) {
  const pp = parsePath(body.path);
  if (!pp) return [400, { error: "path" }];
  const n = await readPost(body.path);
  if (!n) return [404, { error: "gone" }];
  if (!mayChange(user, n.meta)) return [403, { error: "forbidden" }];
  const files = [{ path: body.path, delete: true }];
  // the others in its translation group stop pointing at it
  const rest = { ...(n.meta.translations || {}) };
  delete rest[pp.lang];
  const { found } = await members(pp.type, pp.lang, rest, n.meta.url);
  await retarget(found, rest, files);
  await commit(files, `Delete ${pp.type}: ${oneLine(n.meta.title, 120)} (${user})`, user);
  await notify(`Deleted ${pp.type}: ${oneLine(n.meta.title, 120)}`, `<p>${esc(user)} deleted the ${pp.type} post <b>${esc(n.meta.title)}</b> (${esc(n.meta.url)}).</p>`);
  return [200, { url: n.meta.url }];
}

// photos of a gallery: [{sha, path, w, h, alt, caption}] (new uploads) or [{src, w, h, alt, caption}] (already on the site)
function galleryOf(list) {
  if (list == null || list === "") return { items: [], added: [] };
  if (!Array.isArray(list) || list.length > MAX_GALLERY) return null;
  const items = [], added = [];
  for (const g of list) {
    if (!g || typeof g !== "object") return null;
    let src;
    if (g.sha) {
      if (!/^[0-9a-f]{40}$/.test(g.sha) || !MEDIA_IMAGE.test(g.path || "")) return null;
      src = g.path.replace(/^static/, "");
      added.push({ path: g.path, sha: g.sha });
    } else {
      src = g.src;
      if (!MEDIA_URL.test(src || "") || !/\.(jpg|png|webp)$/i.test(src)) return null;
    }
    const w = Math.round(Number(g.w)), h = Math.round(Number(g.h));
    if (!(w >= 1 && w <= 20000 && h >= 1 && h <= 20000)) return null;
    items.push({ src, w, h, alt: oneLine(g.alt, 200), caption: oneLine(g.caption, 300) });
  }
  return { items, added };
}

// a new post, or (with body.path) changes to an existing one, which keeps its address
async function publish(body, user) {
  const editing = body.path != null;
  let type, lang;
  if (editing) {
    const pp = parsePath(body.path);
    if (!pp) return [400, { error: "path" }];
    ({ type, lang } = pp);
  } else {
    type = body.type == null || body.type === "" ? "news" : body.type;
    lang = body.lang == null || body.lang === "" ? LANGS[0] : body.lang;
    if (!TYPES_LIST.includes(type)) return [400, { error: "posttype" }];
    if (!LANGS.includes(lang)) return [400, { error: "lang" }];
  }
  const old = editing ? await readPost(body.path) : null;
  if (editing && !old) return [404, { error: "gone" }];
  if (editing && !mayChange(user, old.meta)) return [403, { error: "forbidden" }];

  const keep = editing && !editable(old.body);
  const title = oneLine(body.title, 200);
  const html = keep ? old.body : sanitise(String(body.body || "").slice(0, MAX_TEXT));
  const date = validDate(body.date) ? body.date : null;
  const cats = (Array.isArray(body.categories) ? body.categories : []).filter((c) => typeof c === "string" && Object.prototype.hasOwnProperty.call(CATEGORIES, c));
  const files = (Array.isArray(body.files) ? body.files : []).slice(0, 30);
  const video = canonicalVideo(body.video);
  if (video === null) return [400, { error: "video" }];
  const gallery = galleryOf(body.gallery);
  if (!gallery) return [400, { error: "gallery" }];
  const hasText = !!plain(html) || /<img\b|<p class="embed">/.test(html);
  if (!title || !date || !(hasText || (type === "gallery" && (gallery.items.length || video)))) return [400, { error: "missing" }];
  if (body.kind != null && body.kind !== "" && !KINDS.includes(body.kind)) return [400, { error: "kind" }];
  // new uploads come with the blob made by "upload"; files already on the site only by their address
  const bad = (f) => !f || !["image", "attachment", "inline"].includes(f.role) || (f.sha
    ? !/^[0-9a-f]{40}$/.test(f.sha) || !MEDIA_FILE.test(f.path || "")
    : !MEDIA_URL.test(f.url || ""));
  if (files.some(bad)) return [400, { error: "files" }];

  // translations: this post is always part of its own group; linking merges the two groups
  let target = null;
  if (body.translationOf) {
    const tp = parsePath(body.translationOf);
    if (!tp || tp.type !== type || tp.lang === lang || (editing && body.translationOf === body.path)) return [400, { error: "translation" }];
    target = { path: body.translationOf, ...tp, post: await readPost(body.translationOf) };
    if (!target.post) return [404, { error: "gone" }];
  }

  const media = files.map((f) => ({ ...f, url: f.sha ? f.path.replace(/^static/, "") : f.url }));
  const image = media.find((f) => f.role === "image");
  const attachments = media.filter((f) => f.role === "attachment").map((f) =>
    `<p class="file"><a href="${esc(f.url)}">${esc(oneLine(f.label || "Download", 120) || "Download")}</a> (${(f.ext || f.url.split(".").pop()).toUpperCase().replace(/[^A-Z0-9]/g, "")})</p>`).join("\n");
  const added = [...media.filter((f) => f.sha && (f.role !== "inline" || html.includes(f.url))), ...gallery.added]
    .filter((f, i, all) => all.findIndex((g) => g.path === f.path) === i);

  let path, url;
  if (editing) {
    path = body.path; url = old.meta.url;
  } else {
    const Y = date.slice(0, 4), base = BASES[type][lang];
    let slug = slugify(title);
    if (RESERVED_SLUG.test(slug)) slug += "-post";
    let n = 1;
    while (await locate(type, lang, `${base}${slug}${n > 1 ? `-${n}` : ""}/`)) n++;  // the address must be free in every year folder
    if (n > 1) slug += `-${n}`;
    path = `content/${DIR[type]}/${lang}/${Y}/${slug}.html`; url = `${base}${slug}/`;
  }

  const own = { ...((old && old.meta.translations) || {}), [lang]: url };
  let group = own;
  const touched = { found: {}, missing: [] };
  if (target) {
    group = { ...(target.post.meta.translations || {}), [target.lang]: target.post.meta.url };
    for (const [l, u] of Object.entries(own)) {
      if (group[l] && group[l] !== u) return [409, { error: "translation" }];  // that language already has another post in the group
      group[l] = u;
    }
  }
  const ordered = Object.fromEntries(LANGS.filter((l) => group[l]).map((l) => [l, group[l]]));
  if (target) {
    // every other member of the merged group gets the new map; the one the editor named is already known
    const { [target.lang]: _known, ...others } = ordered;
    Object.assign(touched, await members(type, lang, others, url));
    touched.found[target.lang] = target.path;
  }

  const excerpt = oneLine(body.excerpt, 300) || excerptOf(plain(html.replace(/<p class="embed">[\s\S]*?<\/p>/g, "")));
  const imageChanged = !old || old.meta.image !== (image ? image.url : null);
  const meta = { ...(old ? old.meta : {}), type, lang, url, title, translations: ordered, imported: false,
    image: image ? image.url : null, date, excerpt, author: (old && old.meta.author) || user };
  for (const k of ["subtitle", "organisation", "kind", "video", "gallery", "categories", "imageAlt", "imageCredit"]) delete meta[k];
  if (type === "news") {
    const sub = oneLine(body.subtitle, 300);
    if (sub) meta.subtitle = sub;
    meta.categories = cats.length ? cats : [DEFAULT_CATEGORY];
  }
  if (type === "press") { const org = oneLine(body.organisation, 200); if (org) meta.organisation = org; }
  if (type === "gallery") meta.kind = KINDS.includes(body.kind) ? body.kind : video ? "video" : gallery.items.length > 1 ? "album" : "photo";
  if (video) meta.video = video;
  if (gallery.items.length) meta.gallery = gallery.items;
  if (image) {
    const alt = oneLine(body.imageAlt != null ? body.imageAlt : imageChanged ? "" : old.meta.imageAlt, 200);
    const credit = oneLine(body.imageCredit != null ? body.imageCredit : imageChanged ? "" : old.meta.imageCredit, 200);
    if (alt) meta.imageAlt = alt;
    if (credit) meta.imageCredit = credit;
  }
  // a draft is kept in the repository but not built; a future date is built once it has come (scheduled)
  if (body.draft) meta.draft = true; else delete meta.draft;
  // pinning a notice to the home page is the admins' call; an editor's save keeps whatever an admin set
  if (FEATURES.pin && roleOf(user) === "admin" && body.pinned != null) { if (body.pinned) meta.pinned = true; else delete meta.pinned; }
  if (editing) { meta.editedBy = user; meta.modified = localNow(); delete meta.status; }  // edited by staff: no longer an unreviewed import
  const text = keep ? html : html.replace(/<\/(p|h2|h3|ul|ol|blockquote)>/g, "</$1>\n").trim();
  const doc = `---\n${JSON.stringify(meta, null, 1)}\n---\n${text}${attachments ? "\n" + attachments : ""}\n`;

  const out = [{ path, content: doc }, ...added.map((f) => ({ path: f.path, sha: f.sha }))];
  if (target) {
    if (!(await mayRetarget(touched.found, user))) return [403, { error: "forbidden" }];
    await retarget(touched.found, ordered, out);
  }

  const label = type === "gallery" ? "gallery" : type === "press" ? "press release" : "news";
  const what = meta.draft ? `Draft ${label}` : date > localNow() ? `Schedule ${label}` : editing ? `Update ${label}` : `Add ${label}`;
  await commit(out, `${what}: ${title} (${user})`, user);
  const future = date > localNow();
  if (!meta.draft) await notify(`${editing ? "Updated" : "New"} ${label}: ${title}`,
    `<p>${esc(user)} ${editing ? "updated" : "published"} the ${label} post <b>${esc(title)}</b> (${esc(lang)}).</p><p><a href="${BASE_URL}${url}">${BASE_URL}${url}</a> (on the site in about a minute${future ? ", after the date given" : ""})</p>`);
  return [200, { url, path, type, lang, translations: ordered, unlinked: touched.missing, draft: !!meta.draft, scheduled: date.slice(0, 10) > localNow().slice(0, 10) }];
}

// ---------------------------------------------------------------- handler

async function readJson(req) {
  if (req.body && typeof req.body === "object") return req.body;  // Vercel parses JSON bodies
  const chunks = [];
  for await (const c of req) chunks.push(c);
  try { return JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}"); } catch { return {}; }
}

const sameOrigin = (req) => {
  const origin = req.headers.origin;
  if (!origin) return true;
  try { return new URL(origin).host === req.headers.host; } catch { return false; }
};

module.exports = async (req, res) => {
  const send = (status, data) => { res.statusCode = status; res.setHeader("Content-Type", "application/json; charset=utf-8"); res.setHeader("Cache-Control", "no-store"); res.end(JSON.stringify(data)); };
  const info = (user) => ({ user, role: user ? roleOf(user) : null, languages: LANGS, types: TYPES_LIST, kinds: KINDS, categories: categoryLabels(),
    defaultCategory: DEFAULT_CATEGORY, bases: BASES, auth: betterAuth() ? "better-auth" : "password", owner: !!owners[user],
    features: { pin: !!FEATURES.pin && !!user && roleOf(user) === "admin" } });
  if (req.method === "GET") return send(200, info(await session(req)));
  if (req.method !== "POST") { res.setHeader("Allow", "GET, POST"); return send(405, { error: "method" }); }
  if (!sameOrigin(req)) return send(403, { error: "origin" });  // with SameSite=Strict: no cross-site posts
  if (!env("GITHUB_TOKEN") || (!betterAuth() && (!env("NEWS_SECRET") || !Object.keys(users()).length))) return send(503, { error: "config" });

  const body = await readJson(req);
  try {
    if (body.action === "login" && !betterAuth()) {
      const ip = String(req.headers["x-forwarded-for"] || "").split(",")[0] || "?";
      await throttle(ip);
      const all = users();
      const name = Object.keys(all).find((u) => u.toLowerCase() === String(body.name || "").trim().toLowerCase());
      if (!name || !same(all[name].password, String(body.password || ""))) { failures.set(ip, (failures.get(ip) || 0) + 1); return send(401, { error: "login" }); }
      failures.delete(ip);
      const exp = Date.now() + SESSION_HOURS * 3600e3;
      setCookie(res, `${name}|${exp}|${sign(`${name}|${exp}`)}`, SESSION_HOURS * 3600);
      return send(200, info(name));
    }
    if (body.action === "logout") { setCookie(res, "", 0); return send(200, { user: null }); }
    const user = await session(req);
    if (!user) return send(401, { error: "session" });
    if (body.action === "upload") return send(...(await upload(body)));
    if (body.action === "publish") return send(...(await publish(body, user)));
    if (body.action === "load") return send(...(await load(body, user)));
    if (body.action === "delete") return send(...(await remove(body, user)));
    return send(400, { error: "action" });
  } catch (e) {
    console.error(e);
    return send(e && e.status === 400 ? 400 : 502, { error: e && e.status === 400 ? "path" : "server" });
  }
};

module.exports.sanitise = sanitise;
module.exports.slugify = slugify;
module.exports.users = users;
module.exports.canonicalVideo = canonicalVideo;
module.exports.parsePath = parsePath;
module.exports.stemOf = stemOf;
