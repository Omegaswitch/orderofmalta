// /gdpr/ consent forms (static/js/gdpr.js): e-mails the submitted fields to the Order's GDPR address through Resend.
// Nothing is stored and no field value is ever logged (only the form id and the outcome).
// Env: RESEND_API_KEY (required), MAIL_FROM (default web@maltezskyrad.cz), GDPR_TO (default gdpr@maltezskyrad.cz)
const FORMS = {
  "pani-nemocni": "Páni nemocní",
  "dobrovolnici": "Tým a poutníci do Lurd",
  "ostatni": "Dobrovolníci",
  "maltezska-mladez": "Česká maltézská mládež",
  "zmena-osobnich-udaju": "Změna osobních údajů",
};
const MAX_BODY = 64 * 1024, MAX_FIELDS = 60, MAX_LABEL = 200, MAX_VALUE = 5000, MIN_MS = 3000;
const EMAIL = /^[^\s@<>"]+@[^\s@<>"]+\.[^\s@<>"]+$/;

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const env = (k, d = "") => process.env[k] || d;

async function readJson(req) {
  if (req.body && typeof req.body === "object") return req.body;  // Vercel parses JSON bodies
  const chunks = [];
  let size = 0;
  for await (const c of req) { size += c.length; if (size > MAX_BODY) return null; chunks.push(c); }
  try { return JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}"); } catch { return {}; }
}

function message(title, fields, when) {
  const rows = fields.map(([l, v]) => `<tr><th style="text-align:left;vertical-align:top;padding:4px 12px 4px 0;font-weight:600">${esc(l)}</th><td style="padding:4px 0;white-space:pre-wrap">${esc(v) || "–"}</td></tr>`).join("");
  const html = `<h2 style="font-family:sans-serif">Souhlas se zpracováním osobních údajů – ${esc(title)}</h2>
<table style="border-collapse:collapse;font-family:sans-serif;font-size:14px">${rows}</table>
<p style="font-family:sans-serif;font-size:12px;color:#666">Odesláno z formuláře na webu ${esc(when)}. Web údaje neukládá.</p>`;
  const text = `Souhlas se zpracováním osobních údajů – ${title}\n\n` + fields.map(([l, v]) => `${l}: ${v || "–"}`).join("\n") + `\n\nOdesláno z formuláře na webu ${when}. Web údaje neukládá.\n`;
  return { html, text };
}

module.exports = async (req, res) => {
  const send = (status, data) => { res.statusCode = status; res.setHeader("Content-Type", "application/json; charset=utf-8"); res.setHeader("Cache-Control", "no-store"); res.end(JSON.stringify(data)); };
  if (req.method !== "POST") { res.setHeader("Allow", "POST"); return send(405, { error: "method" }); }
  const origin = req.headers.origin;
  try { if (origin && new URL(origin).host !== req.headers.host) return send(403, { error: "origin" }); } catch { return send(403, { error: "origin" }); }
  if (Number(req.headers["content-length"] || 0) > MAX_BODY) return send(413, { error: "size" });

  const body = await readJson(req);
  if (body === null || JSON.stringify(body).length > MAX_BODY) return send(413, { error: "size" });
  const id = String(body.form || "");
  if (!Object.prototype.hasOwnProperty.call(FORMS, id)) return send(400, { error: "form" });
  if (body.hp) { console.log(`gdpr ${id}: honeypot`); return send(400, { error: "spam" }); }
  if (!(Number(body.t) >= MIN_MS)) { console.log(`gdpr ${id}: too fast`); return send(400, { error: "spam" }); }
  const fields = Array.isArray(body.fields) ? body.fields : null;
  if (!fields || !fields.length || fields.length > MAX_FIELDS
      || !fields.every((f) => Array.isArray(f) && f.length === 2 && typeof f[0] === "string" && typeof f[1] === "string" && f[0].length <= MAX_LABEL && f[1].length <= MAX_VALUE)) {
    return send(400, { error: "fields" });
  }
  if (!env("RESEND_API_KEY")) { console.log(`gdpr ${id}: no RESEND_API_KEY`); return send(503, { error: "config" }); }

  const title = FORMS[id];
  const when = new Intl.DateTimeFormat("cs-CZ", { dateStyle: "long", timeStyle: "short", timeZone: "Europe/Prague" }).format(new Date());
  const { html, text } = message(title, fields.map(([l, v]) => [l.trim(), v.trim()]), when);
  const reply = (fields.find(([l]) => l.trim() === "Email") || [])[1];
  const mail = { from: env("MAIL_FROM", "web@maltezskyrad.cz"), to: [env("GDPR_TO", "gdpr@maltezskyrad.cz")],
    subject: `Souhlas se zpracováním osobních údajů – ${title}`, html, text };
  if (reply && EMAIL.test(reply.trim())) mail.reply_to = reply.trim();
  try {
    const r = await fetch("https://api.resend.com/emails", {
      method: "POST", headers: { Authorization: `Bearer ${env("RESEND_API_KEY")}`, "Content-Type": "application/json" }, body: JSON.stringify(mail),
    });
    console.log(`gdpr ${id}: resend ${r.status}`);
    return r.ok ? send(200, { ok: true }) : send(502, { error: "mail" });
  } catch {
    console.log(`gdpr ${id}: resend unreachable`);
    return send(502, { error: "mail" });
  }
};
