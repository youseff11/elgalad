(function () {
  "use strict";
  var root = document.getElementById("batchApp");
  if (!root) return;
  var t = El.t;
  var MAX = parseInt(root.dataset.max, 10) || 32;
  var list = root.querySelector("[data-doc-list]");
  var runBtn = root.querySelector("[data-run]");
  var lastResults = [];

  var SAMPLES = [
    "أعلنت الهيئة العامة للأرصاد الجوية عن استقرار حالة الطقس واعتدال درجات الحرارة على كافة الأنحاء، مع توقعات بسقوط أمطار خفيفة على المناطق الساحلية الشمالية خلال عطلة نهاية الأسبوع، ونصحت المواطنين بمتابعة النشرات الجوية بشكل دوري.",
    "Renewable energy solutions such as solar and wind power are expanding globally to reduce carbon emissions. Governments are offering incentives for clean energy projects, while falling hardware costs make renewables competitive with fossil fuels in many markets.",
    "تسعى الحكومة إلى التحول الرقمي الكامل للخدمات العامة من خلال منصة موحدة تتيح للمواطنين إنجاز معاملاتهم إلكترونياً دون الحاجة إلى زيارة المكاتب الحكومية، مما يقلل الوقت والتكلفة ويعزز الشفافية.",
  ];

  function renumber() {
    var items = list.querySelectorAll(".doc-item");
    items.forEach(function (it, i) { it.querySelector(".doc-num").textContent = i + 1; });
    root.querySelector("[data-doc-count]").textContent = items.length;
    root.querySelector("[data-add-doc]").hidden = items.length >= MAX;
  }

  function addDoc(text) {
    if (list.children.length >= MAX) { El.toast(t("err_batch_limit"), "error"); return null; }
    var it = document.createElement("div");
    it.className = "doc-item";
    it.innerHTML =
      '<span class="doc-num"></span>' +
      '<div><textarea class="input textarea" rows="3" dir="auto" placeholder="' + El.escapeHtml(t("doc_placeholder")) + '"></textarea>' +
      '<div class="doc-meta"><span data-w>0</span> ' + El.escapeHtml(t("words")) + "</div></div>" +
      '<button type="button" class="icon-btn" title="' + El.escapeHtml(t("remove")) + '" data-remove>' +
      '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg></button>';
    var ta = it.querySelector("textarea");
    ta.value = text || "";
    var upd = function () { it.querySelector("[data-w]").textContent = El.fmt(El.words(ta.value)); };
    ta.addEventListener("input", upd); upd();
    it.querySelector("[data-remove]").addEventListener("click", function () {
      if (list.children.length <= 1) { ta.value = ""; upd(); return; }
      it.remove(); renumber();
    });
    list.appendChild(it);
    renumber();
    return ta;
  }

  root.querySelector("[data-add-doc]").addEventListener("click", function () { var ta = addDoc(""); if (ta) ta.focus(); });
  root.querySelector("[data-add-samples]").addEventListener("click", function () {
    // replace empty boxes first
    var empties = Array.prototype.filter.call(list.querySelectorAll("textarea"), function (x) { return !x.value.trim(); });
    SAMPLES.forEach(function (s, i) {
      if (empties[i]) { empties[i].value = s; empties[i].dispatchEvent(new Event("input")); } else addDoc(s);
    });
  });

  root.querySelector("[data-import]").addEventListener("change", async function (e) {
    var files = Array.prototype.slice.call(e.target.files);
    e.target.value = "";
    for (var i = 0; i < files.length; i++) {
      var fd = new FormData(); fd.append("file", files[i]);
      var r = await El.api("/app/api/extract/", { body: fd });
      if (!r.ok) { El.toast(files[i].name + ": " + (r.error || t("err_file_read")), "error"); continue; }
      var empty = Array.prototype.find.call(list.querySelectorAll("textarea"), function (x) { return !x.value.trim(); });
      if (empty) { empty.value = r.text; empty.dispatchEvent(new Event("input")); } else addDoc(r.text);
    }
  });

  function params() {
    var p = {};
    root.querySelectorAll("[data-bparam]").forEach(function (inp) { if (inp.value) p[inp.dataset.bparam] = parseInt(inp.value, 10); });
    return p;
  }

  function renderResults(res) {
    lastResults = res.results;
    var box = root.querySelector("[data-results]");
    root.querySelector("[data-results-meta]").textContent =
      res.count + " " + t("documents") + " · " + El.fmt(res.total_latency_ms / 1000, 2) + t("sec");
    root.querySelector("[data-results-list]").innerHTML = res.results.map(function (r, i) {
      return '<div class="b-row">' +
        '<span class="doc-num">' + (i + 1) + "</span>" +
        '<div class="b-src" dir="auto">' + El.escapeHtml(r.title) + "</div>" +
        '<div class="b-sum" dir="auto">' + El.escapeHtml(r.summary || "—") + "</div>" +
        '<div class="b-meta"><span class="lang-tag lang-' + r.language + '">' + El.escapeHtml(r.language_label) + "</span>" +
        "<span class=\"mono\">" + r.input_words + " → " + r.summary_words + "</span>" +
        "<span class=\"mono\">−" + El.fmt(r.compression, 0) + "%</span>" +
        '<a href="' + r.url + '">' + El.escapeHtml(t("open_details")) + "</a></div>" +
        "</div>";
    }).join("");
    box.hidden = false;
    box.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  runBtn.addEventListener("click", async function () {
    var texts = Array.prototype.map.call(list.querySelectorAll("textarea"), function (x) { return x.value.trim(); })
      .filter(Boolean);
    var errBox = root.querySelector("[data-error]");
    errBox.hidden = true;
    if (!texts.length) { El.toast(t("err_empty"), "error"); return; }
    runBtn.classList.add("is-loading");
    var r = await El.api("/app/api/batch/", { body: { texts: texts, params: params() } });
    runBtn.classList.remove("is-loading");
    if (!r.ok) {
      errBox.querySelector("span").textContent = r.error || t("err_server");
      errBox.hidden = false;
      return;
    }
    renderResults(r);
    El.toast(t("batch_done"), "success");
  });

  root.querySelector("[data-export-csv]").addEventListener("click", function () {
    if (!lastResults.length) return;
    var esc = function (s) { return '"' + String(s == null ? "" : s).replace(/"/g, '""') + '"'; };
    var rows = [["#", "language", "input_words", "summary_words", "compression_%", "summary", "source"]];
    lastResults.forEach(function (r, i) { rows.push([i + 1, r.language, r.input_words, r.summary_words, r.compression, r.summary, r.title]); });
    var csv = "﻿" + rows.map(function (row) { return row.map(esc).join(","); }).join("\n");
    var a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    a.download = "batch-summaries.csv";
    document.body.appendChild(a); a.click(); a.remove();
  });

  addDoc(""); addDoc("");
})();
