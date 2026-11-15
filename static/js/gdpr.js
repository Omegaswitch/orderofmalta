// /gdpr/: sends the filled-in data-protection request form as ordered [label, value] pairs to api/gdpr.js, which e-mails it to
// the address held in the server's settings. Nothing is stored. Messages come from the page's JSON block (#site-data).
// Anti-spam: a hidden honeypot field and a minimum time on the page.
(function () {
  "use strict";
  var loaded = Date.now(), T = {};
  try { T = (JSON.parse(document.getElementById("site-data").textContent) || {}).t || {}; } catch (e) {}
  [].forEach.call(document.querySelectorAll("form.gdpr-form[data-form]"), function (form) {
    var msg = form.querySelector(".ne-msg"), button = form.querySelector('button[type="submit"]');
    if (!msg || !button) return;
    var say = function (text, kind) {
      msg.textContent = text || "";
      msg.className = "ne-msg" + (kind ? " ne-msg--" + kind : "");
      msg.hidden = false;
    };
    form.addEventListener("reset", function () { msg.hidden = true; });
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var elapsed = Date.now() - loaded;
      if (elapsed < 3000) return say(T.gdprTooFast, "error");
      var fields = [];
      [].forEach.call(form.querySelectorAll("[data-label]"), function (el) {
        fields.push([el.getAttribute("data-label"), el.value.trim()]);
      });
      button.disabled = true;
      say(T.gdprSending);
      fetch("/api/gdpr", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ form: form.getAttribute("data-form"), fields: fields, hp: form.elements._hp ? form.elements._hp.value : "", t: elapsed }),
      }).then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (data) { return { ok: r.ok, status: r.status, data: data }; });
      }).then(function (r) {
        if (r.ok) {
          form.reset();
          say(T.gdprSent, "ok");
        } else if (r.status === 503 && r.data.error === "config") {
          say(T.gdprNotSet, "error");
        } else {
          say(T.gdprFailed, "error");
        }
      }, function () {
        say(T.gdprFailed, "error");
      }).then(function () {
        button.disabled = false;
      });
    });
  });
})();
