// Checks api/gdpr.js with Resend stubbed: method, form whitelist, anti-spam, missing configuration, the e-mail sent.
//   node tests/gdpr.test.js
const assert = require("assert");
const handler = require("../api/gdpr.js");
const HOST = "www.orderofmalta.int";

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
const ok = { form: "data-request", hp: "", t: 5000, fields: [["Name", "Jane"], ["Message", "<b>Please</b> erase & forget"], ["E-mail", "jane@example.org"], ["Phone", ""]] };

(async () => {
  assert.strictEqual((await call("GET")).status, 405);
  assert.strictEqual((await call("POST", ok, { origin: "https://evil.example" })).status, 403);
  assert.deepStrictEqual(await call("POST", { ...ok, form: "unknown" }), { status: 400, body: { error: "form" } });
  assert.deepStrictEqual(await call("POST", { ...ok, form: "__proto__" }), { status: 400, body: { error: "form" } });
  assert.deepStrictEqual(await call("POST", { ...ok, hp: "spam" }), { status: 400, body: { error: "spam" } });
  assert.deepStrictEqual(await call("POST", { ...ok, t: 500 }), { status: 400, body: { error: "spam" } });
  assert.deepStrictEqual(await call("POST", { ...ok, fields: [["a", 1]] }), { status: 400, body: { error: "fields" } });
  assert.strictEqual((await call("POST", { ...ok, fields: [["a", "x".repeat(70000)]] })).status, 413);

  // no recipient, sender or key is invented: each missing one is a 503
  for (const k of ["RESEND_API_KEY", "GDPR_TO", "MAIL_FROM"]) delete process.env[k];
  assert.deepStrictEqual(await call("POST", ok), { status: 503, body: { error: "config" } });
  process.env.RESEND_API_KEY = "re_test";
  assert.deepStrictEqual(await call("POST", ok), { status: 503, body: { error: "config" } });
  process.env.GDPR_TO = "privacy@example.test, backup@example.test";
  assert.deepStrictEqual(await call("POST", ok), { status: 503, body: { error: "config" } });
  assert.strictEqual(sent.length, 0);

  process.env.MAIL_FROM = "web@example.test";
  assert.deepStrictEqual(await call("POST", ok), { status: 200, body: { ok: true } });
  const m = sent[0];
  assert.strictEqual(m.headers.Authorization, "Bearer re_test");
  assert.deepStrictEqual(m.body.to, ["privacy@example.test", "backup@example.test"]);
  assert.strictEqual(m.body.from, "web@example.test");
  assert.strictEqual(m.body.subject, "Data protection request");
  assert.strictEqual(m.body.reply_to, "jane@example.org");
  assert.ok(m.body.html.includes("&lt;b&gt;Please&lt;/b&gt; erase &amp; forget"));
  assert.ok(!m.body.html.includes("<b>Please"));
  assert.ok(m.body.text.includes("Message: <b>Please</b> erase & forget"));  // plain text needs no escaping
  assert.match(m.body.text, /Sent from the website form on .*\. The website does not store this data\./);
  assert.ok(!JSON.stringify(m.body).includes("spam"));  // honeypot and timing fields are not mailed
  assert.ok(!("hp" in m.body) && !m.body.text.includes("5000"));

  // the visitor's address is found under a label in any language
  await call("POST", { ...ok, fields: [["Courriel", "marie@example.org"], ["Message", "Bonjour"]] });
  assert.strictEqual(sent[1].body.reply_to, "marie@example.org");
  // no usable e-mail: no reply_to
  await call("POST", { ...ok, fields: [["E-mail", "nope"], ["Message", "change of address"]] });
  assert.strictEqual(sent[2].body.reply_to, undefined);

  console.log("gdpr tests passed");
})().catch((e) => { console.error(e); process.exit(1); });
