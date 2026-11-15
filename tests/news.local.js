// A local stand-in for the hosting: serves dist/ and api/news.js with GitHub replaced by a folder on disk, so the
// whole publishing flow (sign-in, upload, publish, translation linking, edit, delete) can be tried in a browser or by
// a test without a token. Writes go to the repository checkout itself (content/, static/media/), where git shows them.
// /editor/posts.json is generated from content/ on every request (the real build writes it at build time), and when
// dist/ has no editor page yet a bare one is assembled from templates/editor.html, so this works before the first build.
//   node tests/news.local.js [port]      then open http://127.0.0.1:8090/editor/
//   sign-in: editor / editor, admin / admin   (NEWS_USERS, NEWS_SECRET and GITHUB_TOKEN are set here only)
const http = require("http"), fs = require("fs"), path = require("path"), crypto = require("crypto");
const ROOT = path.join(__dirname, "..");
process.env.NEWS_USERS = process.env.NEWS_USERS || "editor:editor\nadmin:admin:admin";
process.env.NEWS_SECRET = process.env.NEWS_SECRET || crypto.randomBytes(16).toString("hex");
process.env.GITHUB_TOKEN = "local";
const blobs = {};  // sha -> bytes, until the commit writes them
global.fetch = async (url, opts = {}) => {
  const u = new URL(url), body = opts.body ? JSON.parse(opts.body) : null;
  const json = (status, data) => ({ ok: status < 300, status, json: async () => data });
  if (u.pathname.includes("/contents/")) {
    const p = path.join(ROOT, decodeURIComponent(u.pathname.split("/contents/")[1]));
    if (!p.startsWith(ROOT + path.sep)) return json(404, {});
    if (fs.existsSync(p) && fs.statSync(p).isDirectory()) return json(200, fs.readdirSync(p, { withFileTypes: true }).map((e) => ({ name: e.name, type: e.isDirectory() ? "dir" : "file" })));
    return fs.existsSync(p) ? json(200, { content: fs.readFileSync(p).toString("base64") }) : json(404, {});
  }
  if (u.pathname.endsWith("/git/blobs")) { const sha = crypto.createHash("sha1").update(body.content).digest("hex"); blobs[sha] = Buffer.from(body.content, "base64"); return json(201, { sha }); }
  if (u.pathname.endsWith("/git/ref/heads/main")) return json(200, { object: { sha: "0".repeat(40) } });
  if (/\/git\/commits\/0+$/.test(u.pathname)) return json(200, { tree: { sha: "1".repeat(40) } });
  if (u.pathname.endsWith("/git/trees")) {
    for (const f of body.tree) {
      const p = path.join(ROOT, f.path);
      if (!p.startsWith(ROOT + path.sep) || !/^(content|static\/media)\//.test(f.path)) throw new Error("outside the allowed folders: " + f.path);
      if (f.sha === null) { if (fs.existsSync(p)) fs.unlinkSync(p); continue; }
      fs.mkdirSync(path.dirname(p), { recursive: true });
      fs.writeFileSync(p, f.content != null ? f.content : blobs[f.sha]);
    }
    return json(201, { sha: "2".repeat(40) });
  }
  if (u.pathname.endsWith("/git/commits")) { console.log("commit:", body.message); return json(201, { sha: "3".repeat(40) }); }
  if (u.pathname.endsWith("/git/refs/heads/main")) return json(200, {});
  if (u.hostname === "api.resend.com") return json(200, {});
  throw new Error("unexpected " + url);
};
const handler = require("../api/news.js");
const TYPES = { ".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript", ".json": "application/json", ".svg": "image/svg+xml", ".webp": "image/webp", ".jpg": "image/jpeg", ".png": "image/png", ".pdf": "application/pdf", ".woff2": "font/woff2", ".xml": "application/xml", ".wasm": "application/wasm" };
const port = Number(process.argv[2] || process.env.PORT || 8090);

// the list the build writes to dist/editor/posts.json, read straight from content/
function postsJson() {
  const out = [];
  for (const [dir, type] of [["news", "news"], ["press", "press"], ["galleries", "gallery"]]) {
    const base = path.join(ROOT, "content", dir);
    if (!fs.existsSync(base)) continue;
    for (const lang of fs.readdirSync(base)) for (const year of fs.readdirSync(path.join(base, lang))) {
      for (const f of fs.readdirSync(path.join(base, lang, year))) {
        if (!f.endsWith(".html")) continue;
        const text = fs.readFileSync(path.join(base, lang, year, f), "utf8"), i = text.indexOf("\n---\n", 4);
        let m; try { m = JSON.parse(text.slice(4, i)); } catch { continue; }
        out.push({ path: `content/${dir}/${lang}/${year}/${f}`, type, lang, url: m.url, title: m.title, date: m.date, author: m.author || null, editedBy: m.editedBy || null,
          draft: !!m.draft, pinned: !!m.pinned, translations: m.translations || {} });
      }
    }
  }
  return out;
}
const shell = () => `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Staff editor (local)</title>
<link rel="stylesheet" href="/css/site.css"><link rel="stylesheet" href="/js/vendor/quill-2.0.3/quill.snow.css"></head><body><main id="main">${fs.readFileSync(path.join(ROOT, "templates", "editor.html"), "utf8")}</main>
<script src="/js/vendor/quill-2.0.3/quill.js"></script><script src="/js/news-editor.js"></script></body></html>`;

http.createServer(async (req, res) => {
  const pathname = decodeURIComponent(req.url.split("?")[0]);
  if (req.url.startsWith("/api/news")) {
    req.headers.host = req.headers.host || `127.0.0.1:${port}`;
    const chunks = []; for await (const c of req) chunks.push(c);
    try { req.body = JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}"); } catch { req.body = {}; }
    const setHeader = res.setHeader.bind(res);
    res.setHeader = (k, v) => setHeader(k, k.toLowerCase() === "set-cookie" ? String(v).replace("; Secure", "") : v);  // plain http locally
    return handler(req, res);
  }
  if (pathname === "/editor/posts.json") { res.setHeader("Content-Type", TYPES[".json"]); return res.end(JSON.stringify(postsJson())); }
  const find = (rel) => [path.join(ROOT, "dist", rel), path.join(ROOT, "static", rel)].find((p) => p.startsWith(ROOT + path.sep) && fs.existsSync(p) && fs.statSync(p).isFile());
  let rel = pathname.replace(/^\/+/, ""); if (!rel || rel.endsWith("/")) rel += "index.html";
  const file = find(rel);
  if (!file && pathname === "/editor/") { res.setHeader("Content-Type", TYPES[".html"]); return res.end(shell()); }
  if (!file) { res.statusCode = 404; return res.end("not found"); }
  res.setHeader("Content-Type", TYPES[path.extname(file)] || "application/octet-stream");
  fs.createReadStream(file).pipe(res);
}).listen(port, "127.0.0.1", () => console.log(`local publishing at http://127.0.0.1:${port}/editor/ (editor/editor, admin/admin); build first with python3 build.py for the real page`));
