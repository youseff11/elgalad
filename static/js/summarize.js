(function () {
  "use strict";
  var root = document.getElementById("summarizeApp");
  if (!root) return;
  var t = El.t;

  var SAMPLES = {
    ar: "أعلنت وزارة التعليم العالي والبحث العلمي عن إطلاق مبادرة وطنية شاملة لتطوير برامج الذكاء الاصطناعي وبناء القدرات الرقمية للطلاب والباحثين في جميع الجامعات، وذلك لمواكبة متطلبات الثورة الصناعية الرابعة وسوق العمل. وتتضمن المبادرة إنشاء مراكز تميز متخصصة في علوم البيانات والتعلم الآلي داخل الجامعات الحكومية، وتقديم منح دراسية للطلاب المتفوقين، إلى جانب عقد شراكات مع كبرى شركات التكنولوجيا العالمية لتوفير برامج تدريب عملي. وأكد الوزير أن المبادرة تستهدف تأهيل أكثر من مئة ألف طالب خلال السنوات الخمس المقبلة، بما يسهم في دعم الاقتصاد الرقمي وتعزيز القدرة التنافسية للكوادر الوطنية.",
    en: "Artificial intelligence and deep learning models have revolutionized modern natural language processing by enabling accurate document abstraction and semantic summarization across large corpora. Transformer-based architectures, which rely on self-attention mechanisms, can capture long-range dependencies between words and sentences far better than earlier recurrent networks. As a result, organizations in education, journalism, law, and research are increasingly adopting automatic summarization tools to process large volumes of text, reduce reading time, and extract key insights. However, challenges remain in ensuring factual consistency and handling low-resource languages with rich morphology, such as Arabic.",
  };

  var PRESETS = {
    short: { max_length: 64, min_length: 10, num_beams: 4, length_penalty: 0.8, repetition_penalty: 1.2, no_repeat_ngram_size: 3 },
    balanced: { max_length: 128, min_length: 25, num_beams: 4, length_penalty: 1.0, repetition_penalty: 1.2, no_repeat_ngram_size: 3 },
    detailed: { max_length: 256, min_length: 60, num_beams: 5, length_penalty: 1.6, repetition_penalty: 1.15, no_repeat_ngram_size: 3 },
  };
  var DEFAULTS = JSON.parse(document.getElementById("param-defaults").textContent);

  var ta = document.getElementById("inputText");
  var submitBtn = root.querySelector("[data-submit]");
  var resultCard = root.querySelector("[data-result]");
  var fileName = "";

  // ---------------------------------------------------------- counters
  function updateCounts() {
    var v = ta.value;
    root.querySelector("[data-count-words]").textContent = El.fmt(El.words(v));
    root.querySelector("[data-count-chars]").textContent = El.fmt(v.length);
    var lang = El.detectLangLocal(v);
    var live = root.querySelector("[data-live-lang]");
    live.innerHTML = lang ? '<span class="lang-tag lang-' + lang + '">' + t("lang_" + lang) + "</span>" : "";
  }
  ta.addEventListener("input", function () { fileName = ""; updateCounts(); });

  // ------------------------------------------------------------- tabs
  root.querySelectorAll("[data-tabs=input] [data-tab]").forEach(function (b) {
    b.addEventListener("click", function () {
      root.querySelectorAll("[data-tabs=input] [data-tab]").forEach(function (x) { x.classList.toggle("active", x === b); });
      root.querySelector("[data-pane=file]").hidden = b.dataset.tab !== "file";
    });
  });

  // ---------------------------------------------------------- samples
  root.querySelectorAll("[data-sample]").forEach(function (b) {
    b.addEventListener("click", function () { ta.value = SAMPLES[b.dataset.sample]; fileName = ""; updateCounts(); ta.focus(); });
  });
  root.querySelector("[data-clear]").addEventListener("click", function () { ta.value = ""; fileName = ""; updateCounts(); ta.focus(); });

  // ------------------------------------------------------------ params
  function paintRange(input) {
    var min = parseFloat(input.min), max = parseFloat(input.max), v = parseFloat(input.value);
    input.style.setProperty("--fill", ((v - min) / (max - min) * 100) + "%");
    var out = input.closest(".param").querySelector("output");
    out.textContent = input.step && input.step.indexOf(".") > -1 ? v.toFixed(input.step.length - 2 > 1 ? 2 : 1) : v;
  }
  function setParams(p) {
    Object.keys(p).forEach(function (k) {
      var inp = root.querySelector('[data-param="' + k + '"] input');
      if (inp) { inp.value = p[k]; paintRange(inp); }
    });
  }
  function getParams() {
    var p = {};
    root.querySelectorAll("[data-param]").forEach(function (el) {
      p[el.dataset.param] = parseFloat(el.querySelector("input").value);
    });
    if (p.min_length >= p.max_length) p.min_length = Math.max(5, p.max_length - 1);
    return p;
  }
  root.querySelectorAll("[data-param] input").forEach(function (inp) {
    inp.addEventListener("input", function () { paintRange(inp); });
  });
  root.querySelectorAll("[data-preset]").forEach(function (b) {
    b.addEventListener("click", function () { setParams(b.dataset.preset === "default" ? DEFAULTS : PRESETS[b.dataset.preset]); });
  });
  setParams(DEFAULTS);

  // ------------------------------------------------------------ upload
  var dz = root.querySelector("[data-dropzone]");
  var fileInput = root.querySelector("[data-file-input]");
  async function handleFile(file) {
    if (!file) return;
    root.querySelector("[data-file-name]").textContent = file.name + " …";
    var fd = new FormData(); fd.append("file", file);
    var r = await El.api("/app/api/extract/", { body: fd });
    if (!r.ok) {
      root.querySelector("[data-file-name]").textContent = "";
      El.toast(r.error || t("err_file_read"), "error");
      return;
    }
    ta.value = r.text; fileName = r.file_name; updateCounts();
    root.querySelector("[data-file-name]").textContent = "✓ " + r.file_name + " · " + El.fmt(r.words) + " " + t("words");
    El.toast(t("file_loaded"), "success");
  }
  fileInput.addEventListener("change", function () { handleFile(fileInput.files[0]); fileInput.value = ""; });
  ["dragenter", "dragover"].forEach(function (ev) {
    dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.add("drag"); });
  });
  ["dragleave", "drop"].forEach(function (ev) {
    dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.remove("drag"); });
  });
  dz.addEventListener("drop", function (e) { handleFile(e.dataTransfer.files[0]); });

  // ------------------------------------------------------------ states
  function show(state) {
    resultCard.querySelectorAll("[data-state]").forEach(function (el) { el.hidden = el.dataset.state !== state; });
    resultCard.querySelector("[data-result-actions]").hidden = state !== "result";
  }
  var stepTimer = null;
  function animateSteps() {
    var steps = resultCard.querySelectorAll(".pstep"), i = 0;
    steps.forEach(function (s) { s.classList.remove("active", "done"); });
    steps[0].classList.add("active");
    clearInterval(stepTimer);
    stepTimer = setInterval(function () {
      if (i < steps.length - 1) { steps[i].classList.remove("active"); steps[i].classList.add("done"); i++; steps[i].classList.add("active"); }
    }, 700);
  }

  function render(r) {
    var q = function (s) { return resultCard.querySelector(s); };
    var lang = q("[data-r-lang]");
    lang.className = "lang-tag lang-" + r.language; lang.textContent = r.language_label;
    q("[data-r-conf]").textContent = r.confidence != null ? t("confidence") + " " + El.fmt(r.confidence * 100, 1) + "%" : t("confidence") + " —";
    q("[data-r-time]").textContent = r.created_at;
    var sumEl = q("[data-r-summary]");
    sumEl.textContent = r.summary || "—";
    sumEl.classList.remove("reveal"); void sumEl.offsetWidth; sumEl.classList.add("reveal");
    q("[data-r-in]").textContent = El.fmt(r.input_words);
    q("[data-r-out]").textContent = El.fmt(r.summary_words);
    q("[data-r-comp]").textContent = El.fmt(r.compression, 1) + "%";
    q("[data-r-lat]").textContent = r.latency_ms ? El.fmt(r.latency_ms / 1000, 2) + t("sec") : "—";
    var keep = r.input_words ? Math.max(2, Math.min(100, r.summary_words / r.input_words * 100)) : 0;
    q("[data-r-bar]").style.width = "0";
    setTimeout(function () { q("[data-r-bar]").style.width = keep + "%"; }, 30);
    q("[data-r-ratio]").textContent = t("ratio_caption").replace("{p}", El.fmt(keep, 0));
    q("[data-r-cleaned]").textContent = r.cleaned_text || "—";
    var cfg = r.params || {};
    q("[data-r-config]").textContent = Object.keys(cfg).map(function (k) { return k + " = " + cfg[k]; }).join("\n") || "—";
    q("[data-download]").href = "/app/history/" + r.id + "/download/";
    q("[data-open]").href = r.url;
    show("result");
  }

  // ------------------------------------------------------------ submit
  var busy = false;
  async function submit() {
    if (busy) return;
    var text = ta.value.trim();
    if (!text) { El.toast(t("err_empty"), "error"); ta.focus(); return; }
    if (El.words(text) < 5) { El.toast(t("err_too_short"), "error"); return; }
    busy = true;
    submitBtn.classList.add("is-loading");
    show("loading"); animateSteps();
    if (window.innerWidth < 1080) resultCard.scrollIntoView({ behavior: "smooth", block: "start" });

    var params = getParams();
    var r = await El.api("/app/api/summarize/", { body: { text: text, params: params, file_name: fileName } });
    if (!r.ok && r.fallback) {
      // Django server can't reach the model → call it from the browser, then save on the server
      var m = await El.modelCall(r.base_url, "/api/v1/summarize", Object.assign({ text: text }, params));
      if (m.ok) {
        r = await El.api("/app/api/summarize/save/", { body: { text: text, params: params, file_name: fileName, data: m.data, latency_ms: m.latency_ms } });
      } else {
        El.logCall(m);
        r = { ok: false, error: m.error };
      }
    }

    clearInterval(stepTimer);
    busy = false;
    submitBtn.classList.remove("is-loading");
    if (!r.ok) {
      resultCard.querySelector("[data-error-text]").textContent = r.error || t("err_server");
      show("error");
      return;
    }
    render(r.result);
    El.toast(t("summary_ready"), "success");
  }
  submitBtn.addEventListener("click", submit);
  resultCard.querySelector("[data-retry]").addEventListener("click", submit);
  ta.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); submit(); }
  });

  updateCounts();
})();
