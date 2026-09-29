/* =====================================================================
   ELGALAD — Chart.js helpers (theme aware, RTL aware)
   Palette: validated categorical reference palette (blue / orange / aqua)
   ===================================================================== */
(function () {
  "use strict";
  if (!window.Chart) return;

  var registry = [];
  var isRTL = document.documentElement.dir === "rtl";

  function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function theme() {
    return {
      text: css("--text-2") || "#475569",
      muted: css("--muted") || "#7c869b",
      grid: css("--grid") || "#e1e0d9",
      surface: css("--surface") || "#fff",
      primary: css("--series-1") || "#2a78d6",
      s1: css("--series-1"), s2: css("--series-2"), s3: css("--series-3"),
    };
  }
  function langColor(code, th) {
    return { ar: th.s1, en: th.s2, mixed: th.s3 }[code] || th.muted;
  }

  function baseOptions(th, extra) {
    var font = { family: getComputedStyle(document.body).fontFamily, size: 12 };
    Chart.defaults.font = font;
    Chart.defaults.color = th.muted;
    return Object.assign({
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 500 },
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          rtl: isRTL,
          textDirection: isRTL ? "rtl" : "ltr",
          backgroundColor: "rgba(15,23,42,.92)",
          titleColor: "#fff", bodyColor: "#e2e8f0",
          padding: 10, cornerRadius: 8, displayColors: true, boxPadding: 4,
        },
      },
    }, extra || {});
  }

  function scales(th, yExtra) {
    return {
      x: { grid: { display: false }, border: { color: th.grid }, ticks: { color: th.muted, maxRotation: 0, autoSkipPadding: 12 } },
      y: Object.assign({
        beginAtZero: true,
        grid: { color: th.grid, drawTicks: false },
        border: { display: false },
        ticks: { color: th.muted, padding: 8, precision: 0 },
      }, yExtra || {}),
    };
  }

  function emptyState(canvas, show) {
    var box = canvas.parentElement;
    var el = box.querySelector(".chart-empty");
    if (show && !el) {
      el = document.createElement("div");
      el.className = "chart-empty";
      el.textContent = (window.El && El.t("chart_no_data")) || "No data yet";
      box.appendChild(el);
    }
    if (el) el.hidden = !show;
    canvas.style.visibility = show ? "hidden" : "visible";
  }

  function make(id, build) {
    var canvas = document.getElementById(id);
    if (!canvas) return null;
    var entry = { id: id, build: build, chart: null };
    var render = function () {
      if (entry.chart) entry.chart.destroy();
      var cfg = build(theme());
      if (!cfg) { emptyState(canvas, true); return; }
      emptyState(canvas, false);
      entry.chart = new Chart(canvas.getContext("2d"), cfg);
    };
    entry.render = render;
    render();
    registry.push(entry);
    return entry;
  }

  document.addEventListener("themechange", function () {
    registry.forEach(function (e) { e.render(); });
  });

  var ElCharts = {
    langColor: langColor,
    theme: theme,

    /* single-series area line (time) */
    line: function (id, points, opts) {
      opts = opts || {};
      return make(id, function (th) {
        if (!points.length || points.every(function (p) { return !p.value; })) return null;
        var color = opts.color ? th[opts.color] : th.primary;
        return {
          type: "line",
          data: {
            labels: points.map(function (p) { return p.label; }),
            datasets: [{
              label: opts.label || "",
              data: points.map(function (p) { return p.value; }),
              borderColor: color, borderWidth: 2,
              pointRadius: points.length > 20 ? 0 : 3, pointHoverRadius: 5,
              pointBackgroundColor: color, pointBorderColor: th.surface, pointBorderWidth: 2,
              tension: 0.35, fill: true,
              backgroundColor: function (ctx) {
                var c = ctx.chart, area = c.chartArea;
                if (!area) return "transparent";
                var g = c.ctx.createLinearGradient(0, area.top, 0, area.bottom);
                g.addColorStop(0, color + "33"); g.addColorStop(1, color + "00");
                return g;
              },
            }],
          },
          options: baseOptions(th, {
            scales: scales(th, opts.unit ? { ticks: { color: th.muted, padding: 8, callback: function (v) { return v + opts.unit; } } } : null),
            plugins: Object.assign(baseOptions(th).plugins, {
              tooltip: Object.assign(baseOptions(th).plugins.tooltip, {
                callbacks: { label: function (c) { return " " + (opts.label ? opts.label + ": " : "") + c.formattedValue + (opts.unit || ""); } },
              }),
            }),
          }),
        };
      });
    },

    /* vertical bars, single series */
    bar: function (id, points, opts) {
      opts = opts || {};
      return make(id, function (th) {
        if (!points.length || points.every(function (p) { return !p.value; })) return null;
        return {
          type: "bar",
          data: {
            labels: points.map(function (p) { return p.label; }),
            datasets: [{
              label: opts.label || "",
              data: points.map(function (p) { return p.value; }),
              backgroundColor: points.map(function (p) { return p.code ? langColor(p.code, th) : th.primary; }),
              borderRadius: { topLeft: 4, topRight: 4 }, borderSkipped: "bottom",
              maxBarThickness: 44, categoryPercentage: 0.7, barPercentage: 0.9,
            }],
          },
          options: baseOptions(th, {
            scales: scales(th, opts.max ? { max: opts.max, ticks: { color: th.muted, padding: 8, callback: function (v) { return v + (opts.unit || ""); } } } : null),
            plugins: Object.assign(baseOptions(th).plugins, {
              tooltip: Object.assign(baseOptions(th).plugins.tooltip, {
                callbacks: { label: function (c) { return " " + c.formattedValue + (opts.unit || ""); } },
              }),
            }),
          }),
        };
      });
    },

    /* horizontal bars (endpoint latency) */
    hbar: function (id, points, opts) {
      opts = opts || {};
      return make(id, function (th) {
        if (!points.length) return null;
        return {
          type: "bar",
          data: {
            labels: points.map(function (p) { return p.label; }),
            datasets: [{
              data: points.map(function (p) { return p.value; }),
              backgroundColor: th.primary, borderRadius: 4, borderSkipped: false, maxBarThickness: 26,
            }],
          },
          options: baseOptions(th, {
            indexAxis: "y",
            interaction: { mode: "nearest", axis: "y", intersect: false },
            scales: {
              x: { beginAtZero: true, grid: { color: th.grid }, border: { display: false }, ticks: { color: th.muted, callback: function (v) { return v + (opts.unit || ""); } } },
              y: { grid: { display: false }, border: { color: th.grid }, ticks: { color: th.text, font: { family: "ui-monospace, Consolas, monospace", size: 11 } } },
            },
            plugins: Object.assign(baseOptions(th).plugins, {
              tooltip: Object.assign(baseOptions(th).plugins.tooltip, {
                callbacks: { label: function (c) { return " " + c.formattedValue + (opts.unit || ""); } },
              }),
            }),
          }),
        };
      });
    },

    /* doughnut by language + external legend */
    doughnut: function (id, points, legendId) {
      return make(id, function (th) {
        var total = points.reduce(function (a, p) { return a + p.count; }, 0);
        var legend = legendId && document.getElementById(legendId);
        if (legend) {
          legend.innerHTML = points.map(function (p) {
            var pct = total ? Math.round(p.count / total * 100) : 0;
            return '<li><i style="background:' + langColor(p.code, th) + '"></i>' + El.escapeHtml(p.label) +
              '<b>' + p.count + ' · ' + pct + '%</b></li>';
          }).join("");
        }
        if (!total) return null;
        return {
          type: "doughnut",
          data: {
            labels: points.map(function (p) { return p.label; }),
            datasets: [{
              data: points.map(function (p) { return p.count; }),
              backgroundColor: points.map(function (p) { return langColor(p.code, th); }),
              borderColor: th.surface, borderWidth: 2, hoverOffset: 6,
            }],
          },
          options: baseOptions(th, { cutout: "68%", interaction: { mode: "nearest", intersect: true } }),
        };
      });
    },
  };

  window.ElCharts = ElCharts;
})();
