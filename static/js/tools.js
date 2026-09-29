(function () {
  "use strict";
  var root = document.getElementById("toolsApp");
  if (!root) return;
  var t = El.t;
  var current = "detect";
  var input = root.querySelector("[data-tool-input]");
  var out = root.querySelector("[data-tool-result]");
  var meta = root.querySelector("[data-tool-meta]");
  var hint = root.querySelector("[data-lang-hint]");
  var runBtn = root.querySelector("[data-run-tool]");

  var SAMPLES = {
    ar: "معالجة اللغة الطبيعية والتعلم العميق في تلخيص النصوص العربية تتطلب مراحل دقيقة من التنظيف والتقطيع.",
    en: "Modern transformer models perform abstractive summarization efficiently across many domains.",
    mixed: "نستخدم مكتبة Transformers مع PyTorch لتدريب الموديل الجديد على بيانات bilingual.",
    html: "<p>أهلاً   وسهلاً    بكم فِي   مَشْرُوعِ التَّلْخِيصِ! https://example.com/test</p>",
  };
  var TITLES = { detect: "tool_detect", clean: "tool_clean", tokenize: "tool_tokenize" };

  root.querySelectorAll("[data-tool]").forEach(function (b) {
    b.addEventListener("click", function () {
      current = b.dataset.tool;
      root.querySelectorAll("[data-tool]").forEach(function (x) { x.classList.toggle("active", x === b); });
      root.querySelector("[data-tool-title]").textContent = t(TITLES[current]);
      hint.hidden = current === "detect";
    });
  });
  root.querySelectorAll("[data-tsample]").forEach(function (b) {
    b.addEventListener("click", function () { input.value = SAMPLES[b.dataset.tsample]; input.focus(); });
  });

  function bar(label, value, color) {
    var pct = Math.round((value || 0) * 1000) / 10;
    return '<div class="ratio-row"><div class="lbl"><span>' + El.escapeHtml(label) + '</span><b class="mono">' + pct + '%</b></div>' +
      '<div class="track"><span style="width:' + pct + "%;background:" + color + '"></span></div></div>';
  }
  function stat(label, value) {
    return '<div class="stat"><span>' + El.escapeHtml(label) + "</span><strong>" + El.escapeHtml(value) + "</strong></div>";
  }

  function render(tool, r, latency) {
    var th = window.ElCharts ? ElCharts.theme() : null;
    var c1 = getComputedStyle(document.documentElement).getPropertyValue("--series-1").trim();
    var c2 = getComputedStyle(document.documentElement).getPropertyValue("--series-2").trim();
    meta.textContent = t("response_time") + ": " + El.fmt(latency) + " ms";
    if (tool === "detect") {
      out.innerHTML =
        '<div class="big-lang"><span class="lang-tag lang-' + r.language + '">' + El.escapeHtml(r.language_label || r.language) + "</span>" +
        "<strong>" + El.fmt((r.confidence || 0) * 100, 1) + '%</strong><span class="muted">' + El.escapeHtml(t("confidence")) + "</span></div>" +
        bar(t("lang_ar"), r.arabic_ratio, c1) + bar(t("lang_en"), r.english_ratio, c2);
    } else if (tool === "clean") {
      var saved = r.original_length ? Math.round((1 - r.cleaned_length / r.original_length) * 100) : 0;
      out.innerHTML =
        '<div class="tool-stats">' + stat(t("original_length"), El.fmt(r.original_length)) + stat(t("cleaned_length"), El.fmt(r.cleaned_length)) +
        stat(t("removed"), saved + "%") + "</div>" +
        '<div class="compare" style="margin-top:16px"><div><h5>' + El.escapeHtml(t("before")) + '</h5><div class="pre" dir="auto">' + El.escapeHtml(input.value) + "</div></div>" +
        "<div><h5>" + El.escapeHtml(t("after")) + ' · <span class="lang-tag lang-' + (r.language_applied || "") + '">' + El.escapeHtml(r.language_label || r.language_applied || "") + '</span></h5><div class="pre after" dir="auto">' + El.escapeHtml(r.cleaned_text) + "</div></div></div>" +
        '<button type="button" class="btn btn-ghost btn-sm" style="margin-top:12px" data-use-cleaned>' + El.escapeHtml(t("use_as_input")) + "</button>";
      out.querySelector("[data-use-cleaned]").addEventListener("click", function () { input.value = r.cleaned_text; });
    } else {
      var s = r.statistics || {};
      out.innerHTML =
        '<div class="tool-stats">' +
        stat(t("lbl_chars"), El.fmt(s.char_count)) + stat(t("lbl_words"), El.fmt(s.word_count)) + stat(t("sentences"), El.fmt(s.sentence_count)) +
        stat(t("subword_tokens"), El.fmt(s.subword_token_count)) + stat(t("avg_word_len"), El.fmt(s.avg_word_length, 1)) +
        stat(t("avg_sentence_len"), El.fmt(s.avg_sentence_length_words, 1)) + "</div>" +
        '<h5 class="muted" style="margin:18px 0 0">' + El.escapeHtml(t("sample_subwords")) + "</h5>" +
        '<div class="subwords" dir="auto">' + (r.sample_subwords || []).map(function (w) { return "<span>" + El.escapeHtml(w) + "</span>"; }).join("") + "</div>";
    }
  }

  async function run() {
    var text = input.value.trim();
    if (!text) { El.toast(t("err_empty"), "error"); input.focus(); return; }
    runBtn.classList.add("is-loading");
    var r = await El.api("/app/api/tool/" + current + "/", { body: { text: text, language: hint.value } });
    runBtn.classList.remove("is-loading");
    if (!r.ok) {
      out.innerHTML = '<div class="alert alert-danger">' + El.escapeHtml(r.error || t("err_server")) + "</div>";
      return;
    }
    render(current, r.result, r.latency_ms);
  }
  runBtn.addEventListener("click", run);
  input.addEventListener("keydown", function (e) { if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); run(); } });
})();
