// maltezskyrad.cz — progressive enhancement only; every page works without this file.
(function () {
  // ---- the menu bar stays at the top once the page scrolls past it (see .site-header.sticky in site.css)
  var header = document.querySelector(".site-header"), bar = header && header.querySelector(".mainnav");
  if (header && bar) {
    var pin = function () {
      var toggle = bar.querySelector(".menu-toggle");
      header.style.setProperty("--stick", bar.offsetTop + "px");
      document.documentElement.style.setProperty("--nav-h", ((toggle && toggle.offsetHeight) || bar.offsetHeight) + "px");
    };
    pin();
    header.classList.add("sticky");
    document.documentElement.classList.add("has-sticky");
    window.addEventListener("resize", pin);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(pin);
  }

  // ---- "coming up" on the home page: remove dates that have passed since the build (CSS shows the first four)
  var today = new Date(); today = new Date(today.getTime() - today.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  [].forEach.call(document.querySelectorAll(".next-list li[data-end]"), function (li) { if (li.getAttribute("data-end") < today) li.remove(); });
  var next = document.querySelector(".home-next");
  if (next && !next.querySelector(".next-list li")) next.remove();

  // ---- main menu (mobile) and submenus
  var toggle = document.querySelector(".menu-toggle");
  var menu = document.getElementById("menu");
  if (toggle && menu) {
    toggle.addEventListener("click", function () {
      var open = toggle.getAttribute("aria-expanded") !== "true";
      toggle.setAttribute("aria-expanded", String(open));
      menu.classList.toggle("open", open);
    });
  }
  document.querySelectorAll(".sub-toggle").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var li = btn.parentElement;
      var open = !li.classList.contains("open");
      li.classList.remove("closed");
      li.classList.toggle("open", open);
      btn.setAttribute("aria-expanded", String(open));
    });
  });
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    document.querySelectorAll(".has-sub.open").forEach(function (li) {
      li.classList.remove("open");
      var b = li.querySelector(".sub-toggle");
      if (b) b.setAttribute("aria-expanded", "false");
    });
    var li = document.activeElement && document.activeElement.closest(".has-sub");
    if (li) {
      if (document.activeElement.closest(".sub")) {
        var top = li.querySelector("a");
        if (top) top.focus();
      }
      li.classList.add("closed");  // focus stays on the item, so :focus-within would keep the submenu open; .closed holds it shut until focus leaves
    }
  });
  document.addEventListener("focusout", function (e) {
    var li = e.target.closest && e.target.closest(".has-sub.closed");
    if (li && !li.contains(e.relatedTarget)) li.classList.remove("closed");
  });
  document.addEventListener("pointerover", function (e) {  // the mouse re-opens it as usual
    var li = e.target.closest && e.target.closest(".has-sub.closed");
    if (li) li.classList.remove("closed");
  });

  // ---- images still downloading develop out of the paper tone once they arrive (see .is-loading)
  document.querySelectorAll("img.ph-img").forEach(function (img) {
    if (img.complete || img.naturalWidth) return;  // already shown (or progressively painting): leave it alone
    img.classList.add("is-loading");
    var done = function () { img.classList.remove("is-loading"); };
    img.addEventListener("load", done, { once: true });
    img.addEventListener("error", done, { once: true });
  });

  // ---- AddCal calendar: load the vendor script only when a calendar is near the viewport
  var widgets = document.querySelectorAll(".cal-widget");
  if (!widgets.length) return;
  var SRC = "https://cdn.addcal.co/embed/v3/calendar.min.js";
  var requested = false;

  function watch(w) {
    var host = w.querySelector("addcal-calendar");
    var started = Date.now();
    (function poll() {
      var root = host && (host.shadowRoot || host);
      if (root && root.querySelector(".addcal-calendar-container, .addcal-calendar-header, .addcal-event")) {
        w.setAttribute("data-state", "ready");
        return;
      }
      if (Date.now() - started > 15000) { w.setAttribute("data-state", "failed"); return; }
      setTimeout(poll, 250);
    })();
  }

  function load() {
    if (requested) return;
    requested = true;
    var s = document.createElement("script");
    s.src = SRC;
    s.async = true;
    s.onerror = function () { widgets.forEach(function (w) { w.setAttribute("data-state", "failed"); }); };
    document.head.appendChild(s);
    widgets.forEach(watch);
  }

  // a page pre-rendered on hover must not contact AddCal until the visitor actually opens it
  if (document.prerendering) { document.addEventListener("prerenderingchange", watchWidgets, { once: true }); return; }
  watchWidgets();

  function watchWidgets() {
    var io = new IntersectionObserver(function (entries) {
      if (entries.some(function (e) { return e.isIntersecting; })) { io.disconnect(); load(); }
    }, { rootMargin: "600px 0px" });
    widgets.forEach(function (w) { io.observe(w); });
  }
})();

// Home, first screen: the news carousel (one slide at a time, moving up; advances every 7 s unless the visitor hovers,
// focuses it, has asked for reduced motion or the tab is hidden) and its tabs (news / coming up).
(function () {
  var box = document.querySelector(".home-feature");
  if (!box) return;
  var track = box.querySelector(".hf-track"), slides = box.querySelectorAll(".hf-slide"), dots = box.querySelectorAll(".hf-dots button");
  var i = 0, timer = null, MS = 7000, still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  function go(n) {
    i = (n + slides.length) % slides.length;
    track.style.transform = "translateY(" + (-100 * i) + "%)";
    slides.forEach(function (s, k) { s.classList.toggle("is-current", k === i); s.inert = k !== i; });
    dots.forEach(function (d, k) { if (k === i) { d.setAttribute("aria-current", "true"); var sp = d.firstChild; sp.style.animation = "none"; sp.offsetHeight; sp.style.animation = ""; } else d.removeAttribute("aria-current"); });
    restart();
  }
  function restart() { clearTimeout(timer); if (!still && !document.getElementById("hf-news").hidden && !box.classList.contains("is-paused") && !document.hidden && slides.length > 1) timer = setTimeout(function () { go(i + 1); }, MS); }
  function pause(p) { box.classList.toggle("is-paused", p); p ? clearTimeout(timer) : restart(); }
  if (slides.length) {
    box.style.setProperty("--hf-ms", MS + "ms");
    if (still) box.classList.add("is-paused");
    dots.forEach(function (d, k) { d.addEventListener("click", function () { go(k); }); });
    box.querySelectorAll(".hf-step").forEach(function (b) { b.addEventListener("click", function () { go(i + Number(b.dataset.step)); }); });
    box.addEventListener("mouseenter", function () { pause(true); });
    box.addEventListener("mouseleave", function () { if (!box.contains(document.activeElement)) pause(false); });
    box.addEventListener("focusin", function () { pause(true); });
    box.addEventListener("focusout", function (e) { if (!box.contains(e.relatedTarget) && !box.matches(":hover")) pause(false); });
    document.addEventListener("visibilitychange", restart);
    go(0);
  }
  var tabs = box.querySelectorAll('[role="tab"]');
  tabs.forEach(function (tab, k) {
    tab.addEventListener("click", function () {
      tabs.forEach(function (t) { var on = t === tab; t.setAttribute("aria-selected", on); t.tabIndex = on ? 0 : -1; document.getElementById(t.getAttribute("aria-controls")).hidden = !on; });
      pause(tab.id !== "hf-tab-news");
    });
    tab.addEventListener("keydown", function (e) {
      if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
      var n = tabs[(k + (e.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length]; n.focus(); n.click();
    });
  });
})();
