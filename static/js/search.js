// Search page (loaded on /search/ and its translations only). The index is one JSON file per language, written by build.py:
// [{"u": url, "t": title, "d": "YYYY-MM-DD", "k": "news|press|gallery|page", "x": text}]. Matching happens here, in the browser.
// Index text is only ever inserted as text nodes (createElement / textContent), never as markup.
(function () {
  "use strict";
  var form = document.querySelector(".search-form"), input = document.getElementById("search-q");
  var box = document.querySelector(".search-results"), list = document.getElementById("search-list"), status = document.querySelector(".search-status");
  if (!form || !input || !box || !list || !status) return;

  var SD = {};
  try { SD = JSON.parse(document.getElementById("site-data").textContent) || {}; } catch (e) {}
  var T = SD.t || {}, LANG = SD.lang || document.documentElement.lang || "en", MAX = 50;
  var indexUrl = (SD.search && SD.search.index) || "/search/index." + LANG + ".json";
  try {
    var v = new URL(document.currentScript.src).searchParams.get("v");
    if (v) indexUrl += "?v=" + encodeURIComponent(v);
  } catch (e) {}

  var fmt = function (s, vars) { return String(s || "").replace(/\{(\w+)\}/g, function (m, k) { return vars && vars[k] != null ? vars[k] : m; }); };
  var strip = function (s) { return String(s).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); };
  var state = function (s, text) { box.setAttribute("data-state", s); status.textContent = text || ""; };

  // normalised text plus, for each normalised character, the index of the original character it came from (to mark hits in the original)
  function fold(text) {
    var out = "", map = [], pos = 0;
    for (var ch of String(text)) {
      var n = strip(ch);
      for (var k = 0; k < n.length; k++) { out += n[k]; map.push(pos); }
      pos += ch.length;
    }
    return { n: out, map: map, len: pos };
  }
  function ranges(text, words) {
    var f = fold(text), found = [];
    words.forEach(function (w) {
      for (var i = f.n.indexOf(w); i > -1; i = f.n.indexOf(w, i + w.length)) {
        found.push([f.map[i], (f.map[i + w.length - 1] || 0) + 1]);
      }
    });
    found.sort(function (a, b) { return a[0] - b[0]; });
    var merged = [];
    found.forEach(function (r) {
      var last = merged[merged.length - 1];
      if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]); else merged.push(r.slice());
    });
    return merged;
  }
  function marked(parent, text, words) {
    var rs = ranges(text, words), at = 0;
    rs.forEach(function (r) {
      if (r[0] > at) parent.appendChild(document.createTextNode(text.slice(at, r[0])));
      var m = document.createElement("mark");
      m.textContent = text.slice(r[0], r[1]);
      parent.appendChild(m);
      at = r[1];
    });
    if (at < text.length) parent.appendChild(document.createTextNode(text.slice(at)));
  }
  function snippet(text, words) {
    if (text.length <= 220) return text;
    var rs = ranges(text, words), from = rs.length ? Math.max(0, rs[0][0] - 70) : 0;
    if (from > 0) { var sp = text.indexOf(" ", from); if (sp > -1 && sp < from + 25) from = sp + 1; }
    var cut = text.slice(from, from + 220), end = cut.lastIndexOf(" ");
    if (from + 220 < text.length && end > 150) cut = cut.slice(0, end);
    return (from > 0 ? "…" : "") + cut + (from + cut.length < text.length ? "…" : "");
  }
  var KIND = { news: "news", press: "pressReleases", gallery: "galleries" };
  function dateText(d) {
    var dt = new Date(d + "T12:00:00");
    if (isNaN(dt)) return d;
    try { return new Intl.DateTimeFormat(LANG === "en" ? "en-GB" : LANG, { day: "numeric", month: "long", year: "numeric" }).format(dt); } catch (e) { return d; }
  }
  function item(row, words) {
    var li = document.createElement("li"), body = document.createElement("div"), meta = document.createElement("p");
    li.className = "card card--" + (row.k === "press" || row.k === "gallery" || row.k === "news" ? row.k : "page");
    body.className = "card-body";
    meta.className = "card-meta";
    if (row.d) {
      var time = document.createElement("time");
      time.setAttribute("datetime", row.d);
      time.textContent = dateText(row.d);
      meta.appendChild(time);
    }
    var label = T[KIND[row.k]];
    if (label) { var kind = document.createElement("span"); kind.className = "card-kind"; kind.textContent = label; meta.appendChild(kind); }
    if (meta.childNodes.length) body.appendChild(meta);
    var h = document.createElement("h2"), a = document.createElement("a");
    h.className = "card-title";
    a.href = row.u;
    marked(a, row.t || row.u, words);
    h.appendChild(a);
    body.appendChild(h);
    if (row.x) { var p = document.createElement("p"); p.className = "card-text"; marked(p, snippet(row.x, words), words); body.appendChild(p); }
    li.appendChild(body);
    return li;
  }

  var index = null, loading = null;
  function load() {
    if (index) return Promise.resolve(index);
    loading = loading || fetch(indexUrl, { credentials: "same-origin" }).then(function (r) {
      if (!r.ok) throw new Error(String(r.status));
      return r.json();
    }).then(function (rows) {
      rows.forEach(function (r) { r._t = strip(r.t || ""); r._a = r._t + " " + strip(r.x || ""); });
      index = rows;
      return rows;
    });
    return loading;
  }
  function find(rows, q) {
    var words = strip(q).split(/\s+/).filter(Boolean);
    var hits = rows.filter(function (r) { return words.every(function (w) { return r._a.indexOf(w) > -1; }); });
    var inTitle = function (r) { return words.every(function (w) { return r._t.indexOf(w) > -1; }) ? 0 : 1; };
    hits = hits.map(function (r, i) { return { r: r, i: i, g: inTitle(r) }; });
    hits.sort(function (a, b) { return a.g - b.g || (b.r.d || "").localeCompare(a.r.d || "") || a.i - b.i; });
    return { words: words, total: hits.length, rows: hits.slice(0, MAX).map(function (h) { return h.r; }) };
  }

  var run = 0;
  function search(q) {
    var mine = ++run;
    q = q.trim();
    list.textContent = "";
    if (!q) { state("idle", ""); return; }
    state("loading", T.searchLoading);
    load().then(function (rows) {
      if (mine !== run) return;
      var res = find(rows, q);
      if (!res.rows.length) { state("empty", T.searchNone); return; }
      res.rows.forEach(function (row) { list.appendChild(item(row, res.words)); });
      state("ready", res.total > res.rows.length ? fmt(T.searchCountOf || T.searchCount, { n: res.rows.length, total: res.total }) : fmt(T.searchCount, { n: res.rows.length }));
    }, function () {
      if (mine !== run) return;
      loading = null;
      state("failed", T.searchFailed);
    });
  }
  var query = function () { try { return new URLSearchParams(location.search).get("q") || ""; } catch (e) { return ""; } };

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var q = input.value.trim();
    try { history.pushState(null, "", q ? "?q=" + encodeURIComponent(q) : location.pathname); } catch (er) {}
    search(q);
  });
  window.addEventListener("popstate", function () { input.value = query(); search(input.value); });
  input.value = query();
  search(input.value);
  if (!input.value) input.focus();
})();
