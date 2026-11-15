// orderofmalta.int — progressive enhancement only; every page works without this file.
// Strings come from the page's own JSON block (#site-data, written by build.py); nothing is fetched from a third party
// except an embedded video, and only after the visitor has clicked it (or has opted in to that provider).
(function () {
  "use strict";

  var SD = {};
  try { SD = JSON.parse(document.getElementById("site-data").textContent) || {}; } catch (e) {}
  var T = SD.t || {};
  var fmt = function (s, vars) { return String(s || "").replace(/\{(\w+)\}/g, function (m, k) { return vars && vars[k] != null ? vars[k] : m; }); };
  var root = document.documentElement;

  // ---- an old search address (?s=term) goes to the search page, for hosts without the redirect rule
  var old = /[?&]s=([^&#]+)/.exec(location.search);
  if (old && SD.search && SD.search.url) { location.replace(SD.search.url + "?q=" + old[1]); return; }

  // ---- the menu bar stays at the top once the page scrolls past it (see .site-header.sticky in site.css)
  var header = document.querySelector(".site-header"), bar = header && header.querySelector(".mainnav");
  if (header && bar) {
    var pin = function () {
      var toggle = bar.querySelector(".menu-toggle");
      header.style.setProperty("--stick", bar.offsetTop + "px");
      root.style.setProperty("--nav-h", ((toggle && toggle.offsetHeight) || bar.offsetHeight) + "px");
    };
    pin();
    header.classList.add("sticky");
    root.classList.add("has-sticky");
    window.addEventListener("resize", pin);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(pin);
  }

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
  // a top-level item that is only a heading (no page of its own) is reachable by keyboard: focus opens its submenu
  document.querySelectorAll(".has-sub>.nav-heading").forEach(function (h) {
    h.tabIndex = 0;
    h.addEventListener("click", function () {
      var li = h.parentElement, open = !li.classList.contains("open");
      li.classList.remove("closed");
      li.classList.toggle("open", open);
      var b = li.querySelector(".sub-toggle");
      if (b) b.setAttribute("aria-expanded", String(open));
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
        var top = li.querySelector(":scope>a, :scope>.nav-heading");
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

  // ---- 404: show the language of the address that was asked for; say so when the item belongs to the archive
  var nf = document.getElementById("not-found");
  if (nf) {
    var sections = [].slice.call(nf.querySelectorAll("section.nf[lang]")), path = location.pathname;
    var chosen = sections.filter(function (s) { return path.indexOf("/" + s.lang + "/") === 0; })[0] || sections[0];
    if (chosen) {
      sections.forEach(function (s) { s.hidden = s !== chosen; });
      root.lang = chosen.lang;
      var h = chosen.querySelector(".display");
      if (h && h.textContent) document.title = h.textContent.trim();
      if ((SD.archiveBases || []).some(function (b) { return path.indexOf(b) === 0; })) {
        var note = chosen.querySelector("[data-archive-note]");
        if (note) note.hidden = false;
      }
    }
  }

  // ---- embedded videos: click to load, with a stored "always" choice per provider
  var CONSENT = "oom-embed-consent", memory = null;
  function consented() {
    if (memory) return memory;
    try { return (localStorage.getItem(CONSENT) || "").split(",").filter(Boolean); } catch (e) { return []; }
  }
  function allow(provider, on) {
    var list = consented().filter(function (p) { return p !== provider; });
    if (on) list.push(provider);
    memory = list;
    try { localStorage.setItem(CONSENT, list.join(",")); } catch (e) {}
  }
  var embeds = [].slice.call(document.querySelectorAll("figure.embed[data-embed]"));
  if (embeds.length) {
    var inView = [];
    var loadEmbed = function (fig, byClick) {
      if (fig.getAttribute("data-state") !== "idle") return;
      var src = fig.getAttribute("data-src");
      if (!src) return;
      if (!byClick) { try { var u = new URL(src); u.searchParams.delete("autoplay"); src = u.toString(); } catch (e) {} }  // an embed opened by scrolling does not start playing
      fig.setAttribute("data-state", "loading");
      var label = fig.querySelector(".embed-title"), frame = document.createElement("iframe"), done = false;
      var ready = function () { if (!done) { done = true; fig.setAttribute("data-state", "ready"); } };
      frame.title = label ? label.textContent.trim() : "";
      frame.setAttribute("allow", "autoplay; encrypted-media; picture-in-picture; fullscreen");
      frame.setAttribute("loading", "lazy");
      frame.setAttribute("referrerpolicy", "strict-origin-when-cross-origin");
      frame.addEventListener("load", ready);
      setTimeout(ready, 20000);  // never leave the skeleton up for good
      fig.insertBefore(frame, fig.querySelector("figcaption"));
      frame.src = src;
      if (byClick) frame.focus();
    };
    var sync = function (provider, on, except) {
      embeds.forEach(function (fig) {
        if (fig.getAttribute("data-embed") !== provider) return;
        var cb = fig.querySelector(".embed-always input");
        if (cb && cb !== except) cb.checked = on;
        if (on && inView.indexOf(fig) > -1) loadEmbed(fig, false);
      });
    };
    embeds.forEach(function (fig) {
      var provider = fig.getAttribute("data-embed"), btn = fig.querySelector(".embed-load"), cb = fig.querySelector(".embed-always input");
      if (btn) btn.addEventListener("click", function () { loadEmbed(fig, true); });
      if (cb) {
        cb.checked = consented().indexOf(provider) > -1;
        cb.addEventListener("change", function () { allow(provider, cb.checked); sync(provider, cb.checked, cb); });
      }
    });
    // with a stored choice, an embed loads as it nears the screen; a page pre-rendered in the background waits until it is shown
    var watch = function () {
      if (!("IntersectionObserver" in window)) return;
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          var fig = en.target, i = inView.indexOf(fig);
          if (en.isIntersecting && i < 0) inView.push(fig);
          if (!en.isIntersecting && i > -1) inView.splice(i, 1);
          if (en.isIntersecting && consented().indexOf(fig.getAttribute("data-embed")) > -1) loadEmbed(fig, false);
        });
      }, { rootMargin: "200px 0px" });
      embeds.forEach(function (fig) { io.observe(fig); });
    };
    if (document.prerendering) document.addEventListener("prerenderingchange", watch, { once: true }); else watch();
  }

  // ---- lightbox: one native <dialog> per page, built on first use; without JavaScript each thumbnail opens its photo
  var box = null, shown = [], at = 0, opener = null, ticket = 0, swipe = null;
  function buildBox() {
    var el = document.createElement("dialog");
    el.className = "lightbox";
    el.setAttribute("data-state", "loading");
    if (T.galleryPhoto) el.setAttribute("aria-label", T.galleryPhoto);
    var skeleton = document.createElement("div");
    skeleton.className = "skeleton lightbox-skeleton";
    skeleton.setAttribute("aria-hidden", "true");
    skeleton.appendChild(document.createElement("span"));
    var fig = document.createElement("figure"), img = document.createElement("img"), cap = document.createElement("figcaption");
    img.alt = "";
    fig.appendChild(img);
    fig.appendChild(cap);
    var btn = function (cls, glyph, label) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = cls;
      b.textContent = glyph;
      if (label) b.setAttribute("aria-label", label);
      return b;
    };
    var close = btn("lightbox-close", "×", T.lightboxClose), prev = btn("lightbox-prev", "‹", T.lightboxPrev), next = btn("lightbox-next", "›", T.lightboxNext);
    var count = document.createElement("p");
    count.className = "lightbox-count";
    count.setAttribute("aria-live", "polite");
    [skeleton, fig, close, prev, next, count].forEach(function (n) { el.appendChild(n); });
    close.addEventListener("click", function () { el.close(); });
    prev.addEventListener("click", function () { go(at - 1); });
    next.addEventListener("click", function () { go(at + 1); });
    el.addEventListener("click", function (e) { if (e.target === el || e.target === fig) el.close(); });
    el.addEventListener("keydown", function (e) {
      if (e.key === "ArrowLeft") { e.preventDefault(); go(at - 1); }
      else if (e.key === "ArrowRight") { e.preventDefault(); go(at + 1); }
    });
    el.addEventListener("pointerdown", function (e) { swipe = e.pointerType === "mouse" ? null : { x: e.clientX, y: e.clientY }; });
    el.addEventListener("pointerup", function (e) {
      if (!swipe) return;
      var dx = e.clientX - swipe.x, dy = e.clientY - swipe.y;
      swipe = null;
      if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) go(at + (dx < 0 ? 1 : -1));
    });
    el.addEventListener("pointercancel", function () { swipe = null; });
    el.addEventListener("close", function () {
      root.classList.remove("lightbox-open");
      img.removeAttribute("src");
      ticket++;
      if (opener && document.contains(opener)) opener.focus();
      opener = null;
    });
    document.body.appendChild(el);
    return { el: el, img: img, cap: cap, count: count, prev: prev, next: next };
  }
  function go(i) {
    if (!shown.length) return;
    at = (i + shown.length) % shown.length;
    var a = shown[at], mine = ++ticket, thumb = a.querySelector("img");
    box.el.setAttribute("data-state", "loading");
    box.count.textContent = fmt(T.lightboxOf || "{i} / {n}", { i: at + 1, n: shown.length });
    box.prev.hidden = box.next.hidden = shown.length < 2;
    var caption = a.getAttribute("data-caption") || "", alt = thumb ? thumb.alt : "";
    box.cap.textContent = caption;
    var w = +a.getAttribute("data-w"), h = +a.getAttribute("data-h");
    var pre = new Image(), settle = function () {
      if (mine !== ticket) return;
      box.img.alt = alt === caption ? "" : alt;
      if (w && h) { box.img.width = w; box.img.height = h; }
      box.img.src = a.href;
      box.el.setAttribute("data-state", "ready");
      [at - 1, at + 1].forEach(function (n) { var s = shown[(n + shown.length) % shown.length]; if (s && s !== a) new Image().src = s.href; });
    };
    pre.onload = pre.onerror = settle;
    pre.src = a.href;
  }
  document.addEventListener("click", function (e) {
    if (e.defaultPrevented || e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var a = e.target.closest && e.target.closest("[data-lightbox] a[href]");
    if (!a || typeof HTMLDialogElement === "undefined") return;
    var group = a.closest("[data-lightbox]");
    e.preventDefault();
    box = box || buildBox();
    shown = [].slice.call(group.querySelectorAll("a[href]"));
    opener = a;
    root.classList.add("lightbox-open");
    if (!box.el.open) box.el.showModal();
    go(shown.indexOf(a));
  });
})();

// Home, first screen: the news carousel (one slide at a time, moving up; advances every 7 s unless the visitor hovers,
// focuses it, has asked for reduced motion or the tab is hidden).
(function () {
  var box = document.querySelector(".home-feature");
  if (!box) return;
  var track = box.querySelector(".hf-track"), slides = box.querySelectorAll(".hf-slide"), dots = box.querySelectorAll(".hf-dots button");
  if (!track || !slides.length) return;
  var i = 0, timer = null, MS = 7000, still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  function go(n) {
    i = (n + slides.length) % slides.length;
    track.style.transform = "translateY(" + (-100 * i) + "%)";
    slides.forEach(function (s, k) { s.classList.toggle("is-current", k === i); s.inert = k !== i; });
    dots.forEach(function (d, k) { if (k === i) { d.setAttribute("aria-current", "true"); var sp = d.firstChild; sp.style.animation = "none"; sp.offsetHeight; sp.style.animation = ""; } else d.removeAttribute("aria-current"); });
    restart();
  }
  function restart() { clearTimeout(timer); if (!still && !box.classList.contains("is-paused") && !document.hidden && slides.length > 1) timer = setTimeout(function () { go(i + 1); }, MS); }
  function pause(p) { box.classList.toggle("is-paused", p); p ? clearTimeout(timer) : restart(); }
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
})();
