// Interactive world map of the Order's presence (home page and Contacts page). No dependencies.
// The container is <div data-worldmap data-svg data-presence data-contacts data-t="{…strings…}"> written by build.py. Without JavaScript the container
// shows the static map image; this script replaces it once world.svg and presence.<lang>.json (both made by tools/make_map.py) have loaded.
// All text from the data is inserted with textContent / createElement, never as markup.
(function () {
  "use strict";
  var root = document.querySelector("[data-worldmap]");
  if (!root || !window.fetch || !window.DOMParser || !window.Promise) return;

  var T = {};
  try { T = JSON.parse(root.getAttribute("data-t")) || {}; } catch (e) {}
  var LANG = document.documentElement.lang || "en";
  var CONTACTS = root.getAttribute("data-contacts") || "";
  var ISO2 = {};
  "ABWAW AFGAF AGOAO AIAAI ALAAX ALBAL ANDAD AREAE ARGAR ARMAM ASMAS ATFTF ATGAG AUSAU AUTAT AZEAZ BDIBI BELBE BENBJ BFABF BGDBD BGRBG BHRBH BHSBS BIHBA BLMBL BLRBY BLZBZ BMUBM BOLBO BRABR BRBBB BRNBN BTNBT BWABW CAFCF CANCA CHECH CHLCL CHNCN CIVCI CMRCM CODCD COGCG COKCK COLCO COMKM CPVCV CRICR CUBCU CUWCW CYMKY CYPCY CZECZ DEUDE DJIDJ DMADM DNKDK DOMDO DZADZ ECUEC EGYEG ERIER ESHEH ESPES ESTEE ETHET FINFI FJIFJ FLKFK FRAFR FROFO FSMFM GABGA GBRGB GEOGE GGYGG GHAGH GINGN GMBGM GNBGW GNQGQ GRCGR GRDGD GRLGL GTMGT GUMGU GUYGY HKGHK HMDHM HNDHN HRVHR HTIHT HUNHU IDNID IMNIM INDIN IOTIO IRLIE IRNIR IRQIQ ISLIS ISRIL ITAIT JAMJM JEYJE JORJO JPNJP KAZKZ KENKE KGZKG KHMKH KIRKI KNAKN KORKR KWTKW LAOLA LBNLB LBRLR LBYLY LCALC LIELI LKALK LSOLS LTULT LUXLU LVALV MACMO MAFMF MARMA MCOMC MDAMD MDGMG MDVMV MEXMX MHLMH MKDMK MLIML MLTMT MMRMM MNEME MNGMN MNPMP MOZMZ MRTMR MSRMS MUSMU MWIMW MYSMY NAMNA NCLNC NERNE NFKNF NGANG NICNI NIUNU NLDNL NORNO NPLNP NRUNR NZLNZ OMNOM PAKPK PANPA PCNPN PERPE PHLPH PLWPW PNGPG POLPL PRIPR PRKKP PRTPT PRYPY PSEPS PYFPF QATQA ROURO RUSRU RWARW SAUSA SDNSD SENSN SGPSG SGSGS SHNSH SLBSB SLESL SLVSV SMRSM SOMSO SPMPM SRBRS SSDSS STPST SURSR SVKSK SVNSI SWESE SWZSZ SXMSX SYCSC SYRSY TCATC TCDTD TGOTG THATH TJKTJ TKMTM TLSTL TONTO TTOTT TUNTN TURTR TWNTW TZATZ UGAUG UKRUA URYUY USAUS UZBUZ VATVA VCTVC VENVE VGBVG VIRVI VNMVN VUTVU WLFWF WSMWS XKXXK YEMYE ZAFZA ZMBZM ZWEZW".split(" ").forEach(function (p) { ISO2[p.slice(0, 3)] = p.slice(3); });

  var PANEL_ORDER = ["order", "diplomatic", "works"];       // groups in the side panel
  var PAINT_ORDER = ["order", "works", "diplomatic"];       // which kind colours a country that has several
  var CHIPS = ["diplomatic", "order", "works"];             // filter chips, left to right
  var LABEL = { diplomatic: T.mapDiplomatic, order: T.mapOrder, works: T.mapWorks };
  var MAXK = 12;
  var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)");

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function fmt(s, n) { return String(s || "").replace("{n}", n); }

  // ---- loading state
  var fallback = root.querySelector(".wm-fallback");
  var skeleton = el("div", "skeleton wm-skeleton");
  skeleton.setAttribute("aria-hidden", "true");
  skeleton.appendChild(el("span"));
  var fimg = fallback && fallback.querySelector("img");
  if (fimg && fimg.getAttribute("width") && fimg.getAttribute("height")) skeleton.style.aspectRatio = fimg.getAttribute("width") + " / " + fimg.getAttribute("height");
  root.setAttribute("data-state", "loading");
  root.appendChild(skeleton);

  function getText(u) { return fetch(u, { credentials: "same-origin" }).then(function (r) { if (!r.ok) throw new Error(u); return r.text(); }); }
  function load() {
    Promise.all([getText(root.getAttribute("data-svg")), getText(root.getAttribute("data-presence"))])
      .then(function (r) { build(r[0], JSON.parse(r[1])); })
      .catch(function () {
        skeleton.remove();
        root.setAttribute("data-state", "failed");
        var p = el("p", "wm-error", T.mapFailed);
        p.setAttribute("role", "status");
        root.appendChild(p);
      });
  }
  // fetch the map data only when the map is near the viewport
  if (window.IntersectionObserver) {
    var near = new IntersectionObserver(function (es) {
      if (es.some(function (x) { return x.isIntersecting; })) { near.disconnect(); load(); }
    }, { rootMargin: "600px 0px" });
    near.observe(root);
  } else load();

  function build(svgText, pres) {
    var doc = new DOMParser().parseFromString(svgText, "image/svg+xml");
    if (doc.getElementsByTagName("parsererror").length) throw new Error("svg");
    var svg = document.importNode(doc.documentElement, true);
    var vb0 = svg.viewBox.baseVal, W = vb0.width, H = vb0.height;
    svg.setAttribute("class", "wm-svg");
    svg.removeAttribute("width");
    svg.removeAttribute("height");
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");

    // ---- names
    var dn = null;
    try { dn = new Intl.DisplayNames([LANG], { type: "region" }); } catch (e) {}
    var names = {};
    function nameOf(iso) {
      if (names[iso]) return names[iso];
      var n = "";
      try { n = (dn && ISO2[iso] && dn.of(ISO2[iso])) || ""; } catch (e) {}
      return (names[iso] = n || iso);
    }
    var collator = new Intl.Collator(LANG);

    // ---- elements per country
    var els = {}, paths = {}, circles = {};
    Array.prototype.forEach.call(svg.querySelectorAll("[data-iso]"), function (n) {
      var iso = n.getAttribute("data-iso");
      (els[iso] = els[iso] || []).push(n);
      (n.tagName.toLowerCase() === "circle" ? circles : paths)[iso] = n;
    });
    var present = Object.keys(pres).filter(function (iso) { return els[iso]; });
    var kindsOf = {};
    present.forEach(function (iso) {
      var set = {};
      pres[iso].entities.forEach(function (e) { set[e.kind] = true; });
      kindsOf[iso] = set;
      els[iso].forEach(function (n) { n.classList.add("is-present"); });
    });
    // Tab order: countries A to Z (a country with a marker is reached through its marker), drawn above the rest
    var countriesG = svg.querySelector("#countries") || svg;
    var hot = document.createElementNS("http://www.w3.org/2000/svg", "g");
    hot.setAttribute("class", "wm-hot");
    countriesG.parentNode.insertBefore(hot, countriesG.nextSibling);
    var byName = present.slice().sort(function (a, b) { return collator.compare(nameOf(a), nameOf(b)); });
    byName.forEach(function (iso) {
      var target = circles[iso] || paths[iso];
      if (paths[iso]) hot.appendChild(paths[iso]);
      target.setAttribute("tabindex", "-1");   // roving tabindex: one Tab stop for all countries (set below)
      target.setAttribute("role", "button");
      target.setAttribute("aria-label", nameOf(iso));
    });
    var markersG = svg.querySelector("#markers");
    if (markersG) {
      byName.forEach(function (iso) { if (circles[iso]) markersG.appendChild(circles[iso]); });
      markersG.parentNode.appendChild(markersG);   // markers on top
    }
    var ring = byName.map(function (iso) { return circles[iso] || paths[iso]; });
    var stop = ring[0];
    if (stop) stop.setAttribute("tabindex", "0");
    function setStop(n) {
      if (n === stop) return;
      if (stop) stop.setAttribute("tabindex", "-1");
      stop = n;
      n.setAttribute("tabindex", "0");
    }
    var markerList = Object.keys(circles).map(function (k) { return circles[k]; });
    var selEl = null, selR = 0;   // outline copy of the selected country, drawn on top

    // ---- interface
    var ui = el("div", "wm-ui");
    var bar = el("div", "wm-bar");
    var chips = el("div", "wm-chips");
    chips.setAttribute("role", "group");
    chips.setAttribute("aria-label", T.mapFilters);
    var active = { diplomatic: true, order: true, works: true };
    var count = el("p", "wm-count");
    count.setAttribute("role", "status");
    CHIPS.forEach(function (k) {
      var b = el("button", "wm-chip");
      b.type = "button";
      b.setAttribute("aria-pressed", "true");
      b.setAttribute("data-k", k);
      b.appendChild(el("span", "wm-swatch"));
      b.appendChild(el("span", "wm-chip-text", LABEL[k]));
      b.addEventListener("click", function () {
        active[k] = !active[k];
        b.setAttribute("aria-pressed", String(active[k]));
        paint();
      });
      chips.appendChild(b);
    });
    bar.appendChild(chips);
    bar.appendChild(count);

    var stage = el("div", "wm-stage");
    var controls = el("div", "wm-controls");
    function ctl(cls, label, glyph, fn) {
      var b = el("button", "wm-btn " + cls);
      b.type = "button";
      b.setAttribute("aria-label", label);
      b.title = label;
      b.appendChild(el("span", "wm-glyph", glyph));
      b.addEventListener("click", fn);
      controls.appendChild(b);
      return b;
    }
    ctl("wm-in", T.mapZoomIn, "+", function () { zoomCentre(1.6); });
    ctl("wm-out", T.mapZoomOut, "−", function () { zoomCentre(1 / 1.6); });
    ctl("wm-reset", T.mapReset, "⤢", function () { animateTo(1, W / 2, H / 2); });

    var keys = el("p", "visually-hidden", T.mapKeys);
    keys.id = "wm-keys";
    var vp = el("div", "wm-viewport");
    vp.tabIndex = 0;
    vp.setAttribute("role", "group");
    vp.setAttribute("aria-label", T.mapLabel);
    vp.setAttribute("aria-describedby", "wm-keys");
    vp.appendChild(svg);
    var tip = el("div", "wm-tip");
    tip.setAttribute("role", "tooltip");
    tip.hidden = true;
    var panel = el("aside", "wm-panel");
    panel.hidden = true;
    stage.appendChild(controls);
    stage.appendChild(vp);
    stage.appendChild(tip);
    stage.appendChild(panel);
    ui.appendChild(bar);
    ui.appendChild(stage);
    ui.appendChild(keys);
    var touch = window.matchMedia && matchMedia("(pointer:coarse)").matches;
    var hintText = (touch && T.mapIntroTouch) || T.mapIntro;
    if (hintText) ui.appendChild(el("p", "wm-hint", hintText));

    root.textContent = "";
    root.appendChild(ui);
    root.setAttribute("data-state", "ready");
    // a marker that sits on another country (Vatican City on Italy, Monaco on France …) lets clicks through until the map is zoomed in
    Object.keys(circles).forEach(function (iso) {
      var c = circles[iso], pt = svg.createSVGPoint();
      pt.x = +c.getAttribute("cx");
      pt.y = +c.getAttribute("cy");
      Object.keys(paths).forEach(function (o) { if (o !== iso && paths[o].isPointInFill(pt)) c.setAttribute("data-over", "1"); });
    });

    // ---- colouring
    function paint() {
      var n = 0;
      present.forEach(function (iso) {
        var kind = null;
        for (var i = 0; i < PAINT_ORDER.length; i++) if (active[PAINT_ORDER[i]] && kindsOf[iso][PAINT_ORDER[i]]) { kind = PAINT_ORDER[i]; break; }
        els[iso].forEach(function (nd) { if (kind) nd.setAttribute("data-k", kind); else nd.removeAttribute("data-k"); });
        if (kind) n++;
      });
      count.textContent = fmt(n === 1 ? T.mapCountOne : T.mapCount, n);
      count.hidden = CHIPS.every(function (c) { return active[c]; });   // all filters on: nothing to report
    }
    paint();

    // ---- view: the SVG viewBox follows (zoom k, centre cx/cy in map units); k = 1 shows the whole map
    var cw = 0, ch = 0, k = 1, cx = W / 2, cy = H / 2, raf = 0;
    function scale0() { return Math.min(cw / W, ch / H); }
    function apply() {
      if (!cw || !ch) return;
      var s = scale0() * k, w = cw / s, h = ch / s;
      cx = w >= W ? W / 2 : Math.min(Math.max(cx, w / 2), W - w / 2);
      cy = h >= H ? H / 2 : Math.min(Math.max(cy, h / 2), H - h / 2);
      svg.setAttribute("viewBox", (cx - w / 2).toFixed(2) + " " + (cy - h / 2).toFixed(2) + " " + w.toFixed(2) + " " + h.toFixed(2));
      var r = Math.min(cw < 500 ? 4.5 : 4, 1.8 + (k - 1) * 1.1) / s;   // markers start small and grow as the map is zoomed in
      selR = r;
      markerList.forEach(function (c) { c.setAttribute("r", r.toFixed(3)); });
      if (selEl && selEl.tagName.toLowerCase() === "circle") selEl.setAttribute("r", (r * 1.35).toFixed(3));
      vp.setAttribute("data-zoomed", k > 1.001 ? "1" : "0");
      vp.setAttribute("data-lo", k < 3 ? "1" : "0");
    }
    function measure() {
      var b = vp.getBoundingClientRect();
      cw = b.width;
      ch = b.height;
      apply();
    }
    if (window.ResizeObserver) new ResizeObserver(measure).observe(vp); else addEventListener("resize", measure);
    measure();

    // keep the map point (ux, uy) under the viewport position (px, py) at zoom nk
    function anchored(nk, ux, uy, px, py) {
      k = Math.min(MAXK, Math.max(1, nk));
      var s = scale0() * k;
      cx = ux - (px - cw / 2) / s;
      cy = uy - (py - ch / 2) / s;
      apply();
    }
    function unitAt(px, py) {
      var s = scale0() * k;
      return [cx + (px - cw / 2) / s, cy + (py - ch / 2) / s];
    }
    function zoomAt(f, clientX, clientY) {
      var b = vp.getBoundingClientRect(), px = clientX - b.left, py = clientY - b.top, u = unitAt(px, py);
      anchored(k * f, u[0], u[1], px, py);
    }
    function zoomCentre(f) { animateTo(k * f, cx, cy); }
    function animateTo(nk, ncx, ncy) {
      nk = Math.min(MAXK, Math.max(1, nk));
      cancelAnimationFrame(raf);
      if (reduce && reduce.matches) { k = nk; cx = ncx; cy = ncy; apply(); return; }
      var k0 = k, x0 = cx, y0 = cy, t0 = performance.now(), D = 260;
      (function step(t) {
        var p = Math.min(1, (t - t0) / D), e = 1 - Math.pow(1 - p, 3);
        k = k0 + (nk - k0) * e;
        cx = x0 + (ncx - x0) * e;
        cy = y0 + (ncy - y0) * e;
        apply();
        if (p < 1) raf = requestAnimationFrame(step);
      })(t0);
    }
    function panBy(fx, fy) {
      var s = scale0() * k;
      animateTo(k, cx + fx * cw / s, cy + fy * ch / s);
    }

    // wheel / trackpad: zoom around the cursor (zooming out at the full view lets the page scroll)
    vp.addEventListener("wheel", function (e) {
      var dy = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaMode === 2 ? e.deltaY * 400 : e.deltaY;
      if (!dy || (k <= 1.001 && dy > 0)) return;
      e.preventDefault();
      cancelAnimationFrame(raf);
      zoomAt(Math.exp(-dy * (e.ctrlKey ? 0.01 : 0.002)), e.clientX, e.clientY);
      hideTip();
    }, { passive: false });

    // pointers: one drags, two pinch
    var ptrs = new Map(), g = null, moved = false, down0 = null;
    function startGesture() {
      var pts = Array.from(ptrs.values()), b = vp.getBoundingClientRect();
      if (!pts.length) { g = null; return; }
      var mx = pts.reduce(function (a, p) { return a + p.x; }, 0) / pts.length - b.left, my = pts.reduce(function (a, p) { return a + p.y; }, 0) / pts.length - b.top;
      g = { u: unitAt(mx, my), k0: k, d0: pts.length > 1 ? Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y) : 0 };
    }
    function doGesture() {
      var pts = Array.from(ptrs.values()), b = vp.getBoundingClientRect();
      if (!g || !pts.length) return;
      var mx = pts.reduce(function (a, p) { return a + p.x; }, 0) / pts.length - b.left, my = pts.reduce(function (a, p) { return a + p.y; }, 0) / pts.length - b.top;
      var ratio = pts.length > 1 && g.d0 ? Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y) / g.d0 : 1;
      anchored(g.k0 * ratio, g.u[0], g.u[1], mx, my);
    }
    vp.addEventListener("pointerdown", function (e) {
      if (e.pointerType === "mouse" && e.button !== 0) return;
      cancelAnimationFrame(raf);
      if (!ptrs.size) { moved = false; down0 = { x: e.clientX, y: e.clientY }; }
      ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY });
      startGesture();
    });
    vp.addEventListener("pointermove", function (e) {
      if (!ptrs.has(e.pointerId)) {
        if (e.pointerType === "mouse") hover(e);
        return;
      }
      ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (!moved && (ptrs.size > 1 || Math.hypot(e.clientX - down0.x, e.clientY - down0.y) > 5)) {
        moved = true;
        hideTip();
        vp.classList.add("is-dragging");
        ptrs.forEach(function (p, id) { try { vp.setPointerCapture(id); } catch (er) {} });
        startGesture();
      }
      if (moved) doGesture();
    });
    function endPointer(e) {
      if (!ptrs.delete(e.pointerId)) return;
      if (ptrs.size) startGesture(); else vp.classList.remove("is-dragging");
    }
    vp.addEventListener("pointerup", endPointer);
    vp.addEventListener("pointercancel", endPointer);
    vp.addEventListener("pointerleave", function (e) { if (e.pointerType === "mouse") hideTip(); });
    vp.addEventListener("click", function (e) {
      if (moved) { moved = false; e.stopPropagation(); return; }
      var n = e.target.closest && e.target.closest("[data-iso]");
      if (n && kindsOf[n.getAttribute("data-iso")]) openPanel(n.getAttribute("data-iso"), n);
    });

    // keyboard
    stage.addEventListener("keydown", function (e) {
      if (e.altKey || e.ctrlKey || e.metaKey) return;
      var t = e.target, key = e.key, iso = t && t.getAttribute && t.getAttribute("data-iso");
      if (key === "Escape") { if (!panel.hidden) { closePanel(true); e.preventDefault(); } return; }
      if (t.closest && t.closest(".wm-panel")) return;
      if ((key === "Enter" || key === " ") && iso && kindsOf[iso]) { e.preventDefault(); openPanel(iso, t); return; }
      var at = iso ? ring.indexOf(t) : -1;
      if (at > -1 && /^(Arrow(Left|Right|Up|Down)|Home|End)$/.test(key)) {   // arrow keys move between countries (A to Z)
        var to = key === "Home" ? 0 : key === "End" ? ring.length - 1 : at + (key === "ArrowLeft" || key === "ArrowUp" ? -1 : 1);
        to = Math.min(Math.max(to, 0), ring.length - 1);
        setStop(ring[to]);
        ring[to].focus();
        e.preventDefault();
        return;
      }
      if (t.closest && t.closest(".wm-bar")) return;
      var step = 0.15;
      if (key === "ArrowLeft") panBy(-step, 0);
      else if (key === "ArrowRight") panBy(step, 0);
      else if (key === "ArrowUp") panBy(0, -step);
      else if (key === "ArrowDown") panBy(0, step);
      else if (key === "+" || key === "=") zoomCentre(1.6);
      else if (key === "-" || key === "_") zoomCentre(1 / 1.6);
      else if (key === "0") animateTo(1, W / 2, H / 2);
      else return;
      e.preventDefault();
    });

    // ---- tooltip
    function showTip(iso, x, y) {
      var b = stage.getBoundingClientRect();
      tip.textContent = nameOf(iso);
      tip.hidden = false;
      var w = tip.offsetWidth, h = tip.offsetHeight;
      tip.style.left = Math.max(4, Math.min(x - b.left - w / 2, b.width - w - 4)) + "px";
      tip.style.top = (y - b.top - h - 14 < 0 ? y - b.top + 18 : y - b.top - h - 14) + "px";
    }
    function hideTip() { tip.hidden = true; }
    function hover(e) {
      var n = e.target.closest && e.target.closest("[data-iso]");
      if (n) showTip(n.getAttribute("data-iso"), e.clientX, e.clientY); else hideTip();
    }
    vp.addEventListener("focusin", function (e) {
      var n = e.target.closest && e.target.closest("[data-iso]");
      if (!n) return;
      if (ring.indexOf(n) > -1) setStop(n);
      var b = n.getBoundingClientRect(), v = vp.getBoundingClientRect();
      if (b.right < v.left || b.left > v.right || b.top < v.top || b.bottom > v.bottom) {   // keyboard focus off screen: bring it in
        var u = unitAt(b.left + b.width / 2 - v.left, b.top + b.height / 2 - v.top);
        animateTo(k, u[0], u[1]);
      }
      var c = n.getBoundingClientRect();
      showTip(n.getAttribute("data-iso"), c.left + c.width / 2, c.top);
    });
    vp.addEventListener("focusout", hideTip);

    // ---- side panel (desktop) / bottom sheet (phone)
    var opener = null, current = null;
    function bboxCentre(iso) {
      var n = paths[iso] || circles[iso], b = n.getBBox();
      return [b.x + b.width / 2, b.y + b.height / 2];
    }
    function openPanel(iso, from) {
      opener = from || opener;
      select(iso);
      panel.textContent = "";
      var head = el("div", "wm-panel-head");
      var h = el("h3", "wm-panel-title", nameOf(iso));
      h.id = "wm-panel-title";
      h.tabIndex = -1;
      var close = el("button", "wm-close");
      close.type = "button";
      close.setAttribute("aria-label", T.mapClose);
      close.title = T.mapClose;
      close.appendChild(el("span", "wm-glyph", "×"));
      close.addEventListener("click", function () { closePanel(true); });
      head.appendChild(h);
      head.appendChild(close);
      panel.appendChild(head);
      var data = pres[iso], body = el("div", "wm-panel-body");
      PANEL_ORDER.forEach(function (kind) {
        var list = data.entities.filter(function (e) { return e.kind === kind; });
        if (!list.length) return;
        var sec = el("section", "wm-group");
        sec.setAttribute("data-k", kind);
        var gh = el("h4", "wm-group-title");
        gh.appendChild(el("span", "wm-swatch"));
        gh.appendChild(el("span", null, LABEL[kind]));
        sec.appendChild(gh);
        var ul = el("ul", "wm-entities");
        list.forEach(function (e) {
          var li = el("li", "wm-entity");
          li.appendChild(el("span", "wm-entity-name", e.name));
          var links = el("span", "wm-entity-links");
          if (e.web) {
            var ext = /^https?:\/\//i.test(e.web);
            var a = el("a", null, T.mapWeb);
            a.href = e.web;
            if (ext) {
              a.target = "_blank";
              a.rel = "noopener";
              a.appendChild(el("span", "visually-hidden", " " + T.mapNewTab));
            }
            links.appendChild(a);
          }
          if (e.email) {
            var m = el("a", null, T.mapEmail);
            m.href = "mailto:" + e.email;
            links.appendChild(m);
          }
          if (links.firstChild) li.appendChild(links);
          ul.appendChild(li);
        });
        sec.appendChild(ul);
        body.appendChild(sec);
      });
      panel.appendChild(body);
      var foot = el("p", "wm-panel-foot");
      var all = el("a", "btn", T.mapAll);
      all.href = CONTACTS + (data.anchor ? "#" + data.anchor : "");
      foot.appendChild(all);
      panel.appendChild(foot);
      panel.setAttribute("role", "dialog");
      panel.setAttribute("aria-labelledby", "wm-panel-title");
      panel.hidden = false;
      root.classList.add("has-panel");
      hideTip();
      if (getComputedStyle(panel).position === "fixed") {   // bottom sheet: bring the map to the top of the screen, above the sheet
        var r = stage.getBoundingClientRect();
        if (r.top < 0 || r.bottom > innerHeight * 0.48) stage.scrollIntoView({ block: "start" });
      }
      showInFreeArea(iso);
      h.focus({ preventScroll: true });
    }
    function showInFreeArea(iso) {   // pan so the country is not hidden behind the panel
      var sb = stage.getBoundingClientRect(), pb = panel.getBoundingClientRect(), v = vp.getBoundingClientRect();
      var left = v.left, right = v.right, top = v.top, bottom = v.bottom;
      if (getComputedStyle(panel).position === "fixed") bottom = Math.min(bottom, pb.top); else right = Math.min(right, pb.left);
      top = Math.max(top, 0);
      if (right - left < 80 || bottom - top < 60) return;
      var c = bboxCentre(iso), s = scale0() * k;
      var px = v.width / 2 + (c[0] - cx) * s + v.left, py = v.height / 2 + (c[1] - cy) * s + v.top;
      var tx = Math.min(Math.max(px, left + 40), right - 40), ty = Math.min(Math.max(py, top + 30), bottom - 30);
      if (Math.abs(tx - px) > 1 || Math.abs(ty - py) > 1) animateTo(k, cx + (px - tx) / s, cy + (py - ty) / s);
    }
    function select(iso) {
      current = iso;
      var n = paths[iso] || circles[iso];
      Array.prototype.forEach.call(svg.querySelectorAll(".is-selected"), function (x) { x.classList.remove("is-selected"); });
      els[iso].forEach(function (x) { x.classList.add("is-selected"); });
      if (selEl) selEl.remove();
      selEl = n.cloneNode(false);
      ["id", "data-iso", "data-k", "tabindex", "role", "aria-label", "class"].forEach(function (a) { selEl.removeAttribute(a); });
      selEl.setAttribute("class", "wm-sel");
      selEl.setAttribute("pointer-events", "none");
      if (selEl.tagName.toLowerCase() === "circle") selEl.setAttribute("r", (selR * 1.35).toFixed(3));
      svg.appendChild(selEl);
    }
    // the phone bottom sheet is fixed to the screen: close it once the map has scrolled out of view
    if (window.IntersectionObserver) new IntersectionObserver(function (es) {
      if (!es[es.length - 1].isIntersecting && !panel.hidden) closePanel(false);
    }).observe(stage);
    function closePanel(restore) {
      panel.hidden = true;
      root.classList.remove("has-panel");
      current = null;
      if (selEl) selEl.remove();
      selEl = null;
      Array.prototype.forEach.call(svg.querySelectorAll(".is-selected"), function (x) { x.classList.remove("is-selected"); });
      if (restore && opener && opener.isConnected && opener.focus) opener.focus({ preventScroll: true });
    }
  }
})();
