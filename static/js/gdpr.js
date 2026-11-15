// /gdpr/ consent forms: sends the filled-in fields as ordered [label, value] pairs to api/gdpr.js, which e-mails
// them to gdpr@maltezskyrad.cz. Nothing is stored. Anti-spam: a hidden honeypot field and a minimum time on the page.
(function () {
  var loaded = Date.now();
  var MAIL = "gdpr@maltezskyrad.cz";
  [].forEach.call(document.querySelectorAll("form.gdpr-form[data-form]"), function (form) {
    var msg = form.querySelector(".ne-msg"), button = form.querySelector('button[type="submit"]');
    var say = function (text, kind) {
      msg.textContent = text;
      msg.className = "ne-msg" + (kind ? " ne-msg--" + kind : "");
      msg.hidden = false;
    };
    form.addEventListener("reset", function () { msg.hidden = true; });
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var elapsed = Date.now() - loaded;
      if (elapsed < 3000) return say("Formulář jste odeslali příliš rychle. Zkontrolujte prosím údaje a odešlete ho znovu.", "error");
      var fields = [];
      [].forEach.call(form.querySelectorAll("[data-label]"), function (el) {
        fields.push([el.getAttribute("data-label"), el.value.trim()]);
      });
      button.disabled = true;
      say("Odesílám…");
      fetch("/api/gdpr", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ form: form.getAttribute("data-form"), fields: fields, hp: form.elements._hp ? form.elements._hp.value : "", t: elapsed }),
      }).then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (data) { return { ok: r.ok, status: r.status, data: data }; });
      }).then(function (r) {
        if (r.ok) {
          form.reset();
          say("Děkujeme, formulář byl odeslán.", "ok");
        } else if (r.status === 503 && r.data.error === "config") {
          say("Formulář zatím není nastavený, pošlete prosím údaje e-mailem na " + MAIL + ".", "error");
        } else {
          say("Formulář se nepodařilo odeslat. Zkuste to prosím znovu, nebo pošlete údaje e-mailem na " + MAIL + ".", "error");
        }
      }, function () {
        say("Formulář se nepodařilo odeslat (chyba připojení). Zkuste to prosím znovu, nebo pošlete údaje e-mailem na " + MAIL + ".", "error");
      }).then(function () {
        button.disabled = false;
      });
    });
  });
})();
