/* =====================================================================
   ELGALAD — shared UI behaviour
   ===================================================================== */
(function () {
  "use strict";

  // ---------------------------------------------------------------- i18n
  var I18N = {};
  try { I18N = JSON.parse(document.getElementById("i18n-data").textContent); } catch (e) {}
  var t = function (k) { return I18N[k] || k; };

  // --------------------------------------------------------------- utils
  function getCookie(name) {
    var m = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return m ? decodeURIComponent(m.pop()) : "";
  }
  function csrf() {
    var el = document.querySelector("[name=csrfmiddlewaretoken]");
    return getCookie("csrftoken") || (el ? el.value : "");
  }
  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmt(n, d) {
    if (n == null || isNaN(n)) return "—";
    return Number(n).toLocaleString("en-US", { minimumFractionDigits: d || 0, maximumFractionDigits: d || 0 });
  }
  function words(s) { s = (s || "").trim(); return s ? s.split(/\s+/).length : 0; }
  function detectLangLocal(s) {
    var ar = (s.match(/[؀-ۿ]/g) || []).length;
    var en = (s.match(/[A-Za-z]/g) || []).length;
    if (!ar && !en) return "";
    var r = ar / (ar + en);
    return r > 0.8 ? "ar" : r < 0.2 ? "en" : "mixed";
  }

  async function api(url, opts) {
    opts = opts || {};
    var headers = { "X-CSRFToken": csrf(), "X-Requested-With": "fetch" };
    var body = opts.body;
    if (body && !(body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(body);
    }
    var resp;
    try {
      resp = await fetch(url, { method: opts.method || (body ? "POST" : "GET"), headers: headers, body: body, credentials: "same-origin" });
    } catch (e) {
      return { ok: false, error: t("err_network") };
    }
    var data = {};
    try { data = await resp.json(); } catch (e) { data = { ok: false, error: t("err_server") + " (" + resp.status + ")" }; }
    if (!resp.ok && data.ok === undefined) data.ok = false;
    return data;
  }

  // -------------------------------------------------------------- toasts
  function toast(text, level) {
    var box = document.getElementById("toasts");
    if (!box) return;
    var el = document.createElement("div");
    el.className = "toast " + (level || "info");
    el.textContent = text;
    box.appendChild(el);
    setTimeout(function () { el.classList.add("out"); setTimeout(function () { el.remove(); }, 260); }, 3600);
  }

  // ---------------------------------------------------------------- theme
  document.addEventListener("click", function (e) {
    var tt = e.target.closest("[data-theme-toggle]");
    if (!tt) return;
    var root = document.documentElement;
    var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("elgalad-theme", next); } catch (err) {}
    document.dispatchEvent(new CustomEvent("themechange", { detail: next }));
  });

  // -------------------------------------------------------------- sidebar
  document.addEventListener("click", function (e) {
    if (e.target.closest("[data-sidebar-open]")) document.body.classList.add("sidebar-open");
    if (e.target.closest("[data-sidebar-close]")) document.body.classList.remove("sidebar-open");
  });

  // ------------------------------------------------------------- dropdown
  document.addEventListener("click", function (e) {
    var toggle = e.target.closest("[data-dropdown-toggle]");
    document.querySelectorAll("[data-dropdown].open").forEach(function (d) {
      if (!toggle || d !== toggle.closest("[data-dropdown]")) d.classList.remove("open");
    });
    if (toggle) toggle.closest("[data-dropdown]").classList.toggle("open");
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      document.querySelectorAll("[data-dropdown].open").forEach(function (d) { d.classList.remove("open"); });
      document.body.classList.remove("sidebar-open");
    }
  });

  // ----------------------------------------------------------- row links
  document.addEventListener("click", function (e) {
    var row = e.target.closest("tr[data-href]");
    if (row && !e.target.closest("a, button, form")) window.location = row.getAttribute("data-href");
  });

  // ---------------------------------------------------------------- copy
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-copy-target]");
    if (!btn) return;
    var el = document.querySelector(btn.getAttribute("data-copy-target"));
    if (!el) return;
    var text = el.innerText.trim();
    var done = function () { toast(t("copied"), "success"); };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(done, function () { fallbackCopy(text); done(); });
    } else { fallbackCopy(text); done(); }
  });
  function fallbackCopy(text) {
    var ta = document.createElement("textarea");
    ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); } catch (e) {}
    ta.remove();
  }

  // ------------------------------------------------------ confirm forms
  document.addEventListener("submit", function (e) {
    var msg = e.target.getAttribute("data-confirm");
    if (msg && !window.confirm(msg)) e.preventDefault();
  });

  // ------------------------------------------------------------ favorite
  document.addEventListener("click", async function (e) {
    var btn = e.target.closest("[data-fav-url]");
    if (!btn) return;
    e.preventDefault();
    var res = await api(btn.getAttribute("data-fav-url"), { method: "POST" });
    if (res.ok) {
      btn.classList.toggle("on", res.favorite);
      toast(res.favorite ? t("fav_added") : t("fav_removed"), "success");
    }
  });

  // --------------------------------------------------------- model health
  var healthBusy = false;
  async function checkHealth(force) {
    var pills = document.querySelectorAll("[data-health-pill]");
    var boxes = document.querySelectorAll("[data-health-box]");
    if (!pills.length && !boxes.length) return;
    if (healthBusy) return;
    healthBusy = true;
    boxes.forEach(function (b) {
      var lbl = b.querySelector("[data-health-label]");
      if (lbl) lbl.textContent = t("checking");
    });
    var r = await api("/app/api/health/" + (force === true ? "?force=1" : ""));
    healthBusy = false;
    var ok = !!r.ok;
    var state = ok ? "ok" : "bad";
    var label = ok ? t("model_online") : (r.reachable ? t("model_not_loaded") : t("model_offline"));

    pills.forEach(function (p) {
      p.classList.remove("ok", "bad"); p.classList.add(state);
      var txt = p.querySelector("[data-health-text]");
      if (txt) txt.textContent = ok ? label + " · " + fmt(r.latency_ms) + " ms" : label;
    });
    boxes.forEach(function (b) {
      var dot = b.querySelector("[data-health-dot]");
      if (dot) { dot.classList.remove("ok", "bad"); dot.classList.add(state); }
      var lbl = b.querySelector("[data-health-label]");
      if (lbl) lbl.textContent = label;
      var info = r.info || {};
      b.querySelectorAll("[data-info]").forEach(function (dd) {
        var k = dd.getAttribute("data-info");
        var v = k === "latency" ? (r.latency_ms != null ? fmt(r.latency_ms) + " ms" : "—") : info[k];
        if (Array.isArray(v)) v = v.map(function (x) { return x.toUpperCase(); }).join(" · ");
        dd.textContent = v || "—";
      });
    });
    if (!ok && r.error && document.querySelector("[data-health-refresh]._clicked")) toast(r.error, "error");
    document.querySelectorAll("[data-health-refresh]._clicked").forEach(function (b) { b.classList.remove("_clicked"); });
  }
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-health-refresh]");
    if (b) { b.classList.add("_clicked"); checkHealth(true); }
  });

  // ---------------------------------------------------------- public nav
  var pubnav = document.querySelector("[data-pubnav]");
  if (pubnav) {
    var onScroll = function () { pubnav.classList.toggle("scrolled", window.scrollY > 8); };
    window.addEventListener("scroll", onScroll, { passive: true }); onScroll();
  }

  // --------------------------------------------------------------- boot
  document.addEventListener("DOMContentLoaded", function () {
    (window.__FLASH || []).forEach(function (m) { toast(m.text, m.level.indexOf("error") > -1 ? "error" : "success"); });
    checkHealth();
    setInterval(checkHealth, 60000);
  });

  // expose helpers for page scripts
  window.El = { t: t, api: api, toast: toast, fmt: fmt, words: words, escapeHtml: escapeHtml, detectLangLocal: detectLangLocal };
})();
