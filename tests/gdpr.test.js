// Checks api/gdpr.js with Resend stubbed: method, form whitelist, anti-spam, missing key, the e-mail sent.
//   node tests/gdpr.test.js
const assert = require("assert");
const handler = require("../api/gdpr.js");
const HOST = "www.maltezskyrad.cz";

const sent = [];
global.fetch = async (url, opts) => {
  assert.strictEqual(url, "https://api.resend.com/emails");
  sent.push({ headers: opts.headers, body: JSON.parse(opts.body) });
  return { ok: true, status: 200, json: async () => ({ id: "x" }) };
};

function call(method, body, headers = {}) {
  return new Promise((done) => {
    const res = { statusCode: 200, h: {}, setHeader(k, v) { this.h[k.toLowerCase()] = v; }, end(s) { done({ status: this.statusCode, body: JSON.parse(s || "{}") }); } };
    handler({ method, headers: { host: HOST, origin: `https://${HOST}`, ...headers }, body }, res);
  });
}
const ok = { form: "pani-nemocni", hp: "", t: 5000, fields: [["Jméno", "Jan"], ["Příjmení", "<b>Novák</b> & syn"], ["Email", "jan@example.cz"], ["Telefon", ""]] };

(async () => {
  assert.strictEqual((await call("GET")).status, 405);
  assert.strictEqual((await call("POST", ok, { origin: "https://evil.example" })).status, 403);
  assert.deepStrictEqual(await call("POST", { ...ok, form: "neznamy" }), { status: 400, body: { error: "form" } });
  assert.deepStrictEqual(await call("POST", { ...ok, form: "__proto__" }), { status: 400, body: { error: "form" } });
  assert.deepStrictEqual(await call("POST", { ...ok, hp: "spam" }), { status: 400, body: { error: "spam" } });
  assert.deepStrictEqual(await call("POST", { ...ok, t: 500 }), { status: 400, body: { error: "spam" } });
  assert.deepStrictEqual(await call("POST", { ...ok, fields: [["a", 1]] }), { status: 400, body: { error: "fields" } });
  assert.strictEqual((await call("POST", { ...ok, fields: [["a", "x".repeat(70000)]] })).status, 413);

  delete process.env.RESEND_API_KEY;
  assert.deepStrictEqual(await call("POST", ok), { status: 503, body: { error: "config" } });
  assert.strictEqual(sent.length, 0);

  process.env.RESEND_API_KEY = "re_test";
  assert.deepStrictEqual(await call("POST", ok), { status: 200, body: { ok: true } });
  const m = sent[0];
  assert.strictEqual(m.headers.Authorization, "Bearer re_test");
  assert.deepStrictEqual(m.body.to, ["gdpr@maltezskyrad.cz"]);
  assert.strictEqual(m.body.from, "web@maltezskyrad.cz");
  assert.strictEqual(m.body.subject, "Souhlas se zpracováním osobních údajů – Páni nemocní");
  assert.strictEqual(m.body.reply_to, "jan@example.cz");
  assert.ok(m.body.html.includes("&lt;b&gt;Novák&lt;/b&gt; &amp; syn"));
  assert.ok(!m.body.html.includes("<b>Novák"));
  assert.ok(m.body.text.includes("Příjmení: <b>Novák</b> & syn"));  // plain text needs no escaping
  assert.ok(!JSON.stringify(m.body).includes("spam"));  // honeypot and timing fields are not mailed
  assert.ok(!("hp" in m.body) && !m.body.text.includes("5000"));

  // no usable e-mail: no reply_to
  await call("POST", { ...ok, form: "zmena-osobnich-udaju", fields: [["Email", "nope"], ["Změna", "nová adresa"]] });
  assert.strictEqual(sent[1].body.reply_to, undefined);
  assert.strictEqual(sent[1].body.subject, "Souhlas se zpracováním osobních údajů – Změna osobních údajů");

  console.log("gdpr tests passed");
})().catch((e) => { console.error(e); process.exit(1); });
