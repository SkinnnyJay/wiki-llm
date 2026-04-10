/**
 * Loads docs/memory/metrics-dashboard.json and renders Chart.js figures.
 * Update the JSON when benchmark runs land (keep in sync with comparisons.md).
 */
(function () {
  var JSON_URL = './metrics-dashboard.json';

  var colors = {
    accent: '#38bdf8',
    accent2: '#a78bfa',
    muted: '#8b9cb3',
    text: '#e8edf7',
    grid: 'rgba(148, 163, 184, 0.2)',
    warn: '#fbbf24'
  };

  function setStatus(el, text, isError) {
    if (!el) return;
    el.textContent = text;
    el.style.color = isError ? '#f87171' : colors.muted;
  }

  function clearList(el) {
    while (el && el.firstChild) {
      el.removeChild(el.firstChild);
    }
  }

  function buildCharts(data) {
    if (typeof Chart === 'undefined') {
      return;
    }
    Chart.defaults.color = colors.muted;
    Chart.defaults.borderColor = colors.grid;
    Chart.defaults.font.family = '"DM Sans", system-ui, sans-serif';

    var lme = data.lme || {};
    var target = lme.target_recall_at_5 != null ? lme.target_recall_at_5 : 1.0;
    var current = lme.recall_at_5;

    var barEl = document.getElementById('chart-lme-target');
    if (barEl && current != null) {
      new Chart(barEl, {
        type: 'bar',
        data: {
          labels: ['PLAN target R@5', 'wiki-llm LME R@5 (N=' + (lme.limit || '?') + ')'],
          datasets: [
            {
              label: 'R@5',
              data: [target, current],
              backgroundColor: [colors.accent2, colors.accent],
              borderWidth: 0,
              borderRadius: 6
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          aspectRatio: 1.6,
          plugins: {
            legend: { display: false },
            title: {
              display: true,
              text: 'LME: current vs goal (same metric)',
              color: colors.text,
              font: { size: 14, weight: '600' }
            },
            tooltip: {
              callbacks: {
                label: function (ctx) {
                  return 'R@5: ' + ctx.parsed.y;
                }
              }
            }
          },
          scales: {
            y: {
              min: 0.9,
              max: 1.0,
              ticks: { stepSize: 0.02 },
              grid: { color: colors.grid }
            },
            x: { grid: { display: false } }
          }
        }
      });
    }

    var histEl = document.getElementById('chart-history');
    var hist = data.history || [];
    if (histEl && hist.length > 0) {
      var labels = hist.map(function (h) {
        return h.date || '';
      });
      var vals = hist.map(function (h) {
        return h.recall_at_5;
      });
      new Chart(histEl, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [
            {
              label: 'R@5',
              data: vals,
              borderColor: colors.accent,
              backgroundColor: 'rgba(56, 189, 248, 0.12)',
              fill: true,
              tension: 0.2,
              pointRadius: 5,
              pointBackgroundColor: colors.accent
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          aspectRatio: 1.8,
          plugins: {
            legend: { display: false },
            title: {
              display: true,
              text:
                hist.length > 1
                  ? 'Trend (append dated rows to metrics-dashboard.json)'
                  : 'Trend (add more history entries to see a line)',
              color: colors.text,
              font: { size: 14, weight: '600' }
            },
            tooltip: {
              callbacks: {
                afterLabel: function (ctx) {
                  var row = hist[ctx.dataIndex];
                  if (row && row.failures != null) {
                    return 'Failures: ' + row.failures;
                  }
                  return '';
                }
              }
            }
          },
          scales: {
            y: {
              min: 0.9,
              max: 1.0,
              grid: { color: colors.grid }
            },
            x: { grid: { display: false } }
          }
        }
      });
    }

    var bucketEl = document.getElementById('chart-buckets');
    var fb = lme.failure_buckets;
    if (bucketEl && fb && typeof fb === 'object') {
      var bk = ['P', 'R', 'M', 'L'];
      var bv = bk.map(function (k) {
        return fb[k] != null ? fb[k] : 0;
      });
      var hasAny = bv.some(function (n) {
        return n > 0;
      });
      if (hasAny) {
        new Chart(bucketEl, {
          type: 'doughnut',
          data: {
            labels: ['P (parse)', 'R (retrieval)', 'M (multi)', 'L (LLM/env)'],
            datasets: [
              {
                data: bv,
                backgroundColor: ['#64748b', colors.accent, colors.accent2, colors.warn],
                borderWidth: 0
              }
            ]
          },
          options: {
            responsive: true,
            maintainAspectRatio: true,
            aspectRatio: 1.4,
            plugins: {
              legend: {
                position: 'bottom',
                labels: { boxWidth: 12, padding: 10 }
              },
              title: {
                display: true,
                text: 'LME miss buckets (latest N=' + (lme.limit || '?') + ' run)',
                color: colors.text,
                font: { size: 14, weight: '600' }
              }
            }
          }
        });
      } else {
        bucketEl.parentElement.style.display = 'none';
      }
    }

    var otherEl = document.getElementById('chart-other-suites');
    var others = data.wiki_llm_other_suites || [];
    if (otherEl && others.length > 0) {
      new Chart(otherEl, {
        type: 'bar',
        data: {
          labels: others.map(function (o) {
            return o.suite + ' ' + o.metric + ' (N=' + (o.limit || '?') + ')';
          }),
          datasets: [
            {
              label: 'Score',
              data: others.map(function (o) {
                return o.value;
              }),
              backgroundColor: colors.accent2,
              borderWidth: 0,
              borderRadius: 6
            }
          ]
        },
        options: {
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: true,
          aspectRatio: 1.4,
          plugins: {
            legend: { display: false },
            title: {
              display: true,
              text: 'Other wiki-llm suite snapshots (different metrics)',
              color: colors.text,
              font: { size: 14, weight: '600' }
            },
            tooltip: {
              callbacks: {
                afterLabel: function (ctx) {
                  var row = others[ctx.dataIndex];
                  return row && row.note ? row.note : '';
                }
              }
            }
          },
          scales: {
            x: { min: 0, max: 1, grid: { color: colors.grid } },
            y: { grid: { display: false } }
          }
        }
      });
    }
  }

  function renderExternals(data) {
    var list = document.getElementById('metrics-externals-list');
    if (!list || !data.externals) return;
    clearList(list);
    data.externals.forEach(function (ex) {
      var li = document.createElement('li');
      var a = document.createElement('a');
      a.href = ex.url || '#';
      a.textContent = ex.name || 'Link';
      a.rel = 'noopener noreferrer';
      li.appendChild(a);
      if (ex.note) {
        li.appendChild(document.createTextNode(' — ' + ex.note));
      }
      list.appendChild(li);
    });
  }

  function run() {
    var statusEl = document.getElementById('metrics-dashboard-status');
    var headlineEl = document.getElementById('metrics-headline');
    setStatus(statusEl, 'Loading metrics…', false);

    fetch(JSON_URL)
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (data) {
        if (headlineEl && data.headline) {
          headlineEl.textContent = data.headline;
        }
        var updated = data.updated || 'unknown';
        setStatus(
          statusEl,
          'Data updated ' +
            updated +
            '. Commit metrics-dashboard.json after each serious benchmark run (see comparisons.md).',
          false
        );
        renderExternals(data);
        buildCharts(data);
      })
      .catch(function (err) {
        setStatus(
          statusEl,
          'Could not load metrics-dashboard.json (' + (err && err.message ? err.message : 'error') + '). Open the repo locally or check Pages deployment.',
          true
        );
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run);
  } else {
    run();
  }
})();
