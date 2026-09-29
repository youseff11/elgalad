(function () {
  "use strict";
  var raw = document.getElementById("dashboard-data");
  if (!raw || !window.ElCharts) return;
  var d = JSON.parse(raw.textContent);

  ElCharts.bar("chartActivity",
    d.activity.map(function (p) { return { label: p.date, value: p.count }; }),
    { label: El.t("summaries") });

  ElCharts.doughnut("chartLanguages", d.languages, "langLegend");

  ElCharts.line("chartLatency", d.latency, { label: El.t("response_time"), unit: "s" });

  ElCharts.bar("chartCompression",
    d.compression.map(function (p) { return { label: p.label, value: p.value, code: p.code }; }),
    { unit: "%", max: 100 });
})();
