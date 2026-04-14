/**
 * Loads docs/memory/metrics-dashboard.json and renders Chart.js figures.
 * Update metrics-dashboard.json when you publish serious benchmark numbers (keep narrative aligned with benchmarks/README.md).
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
      var statusEl0 = document.getElementById('metrics-dashboard-status');
      setStatus(
        statusEl0,
        'Chart.js did not load (check network or CDN). Charts are unavailable; links and prose below still work.',
        true
      );
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

  function renderPeerLme(data) {
    var card = document.getElementById('peer-lme-card');
    var pl = data.peer_lme;
    if (!card || !pl) return;
    var sum = document.getElementById('peer-lme-summary');
    if (sum && pl.summary) {
      sum.textContent = pl.summary;
    }
    var tbody = document.getElementById('peer-lme-tbody');
    var rows = pl.editorial_reference_overall_10 || [];
    if (tbody && rows.length > 0) {
      clearList(tbody);
      rows.forEach(function (row) {
        var tr = document.createElement('tr');
        var ov = row.overall;
        var dsia = [row.data_integrity, row.simplicity, row.integration, row.arch_maturity];
        var dsiaStr = dsia.every(function (x) {
          return x == null;
        })
          ? '—'
          : dsia
              .map(function (x) {
                return x == null ? '—' : String(x);
              })
              .join(' / ');
        var r5 = row.lme_r_at_5;
        var r5Str = r5 == null ? 'Run locally' : String(r5);

        var td0 = document.createElement('td');
        td0.textContent = row.peer || '';
        var td1 = document.createElement('td');
        td1.textContent = ov == null ? '—' : String(ov);
        var td2 = document.createElement('td');
        td2.textContent = dsiaStr;
        var td3 = document.createElement('td');
        td3.textContent = r5Str;

        tr.appendChild(td0);
        tr.appendChild(td1);
        tr.appendChild(td2);
        tr.appendChild(td3);
        tbody.appendChild(tr);
      });
    }
    var foot = document.getElementById('peer-lme-footnote');
    if (foot) {
      foot.textContent =
        'D / S / I / A = Data Integrity, Simplicity, Integration, Arch Maturity. Editorial numbers are for comparison tables; run llm-wiki benchmark run lme --peer … to measure LME R@5 and write benchmark.peer.* metrics.';
    }
    card.hidden = false;
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

  function setGridLoading(loading, isError) {
    var grid = document.getElementById('memory-metrics-grid');
    if (!grid) return;
    grid.classList.toggle('memory-metrics-grid--loading', !!loading);
    grid.classList.toggle('memory-metrics-grid--error', !!isError);
    grid.setAttribute('aria-busy', loading ? 'true' : 'false');
  }

  function run() {
    var statusEl = document.getElementById('metrics-dashboard-status');
    var headlineEl = document.getElementById('metrics-headline');
    setStatus(statusEl, 'Loading metrics…', false);
    setGridLoading(true, false);

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
            '. Commit metrics-dashboard.json after each serious benchmark run (see benchmarks/README.md in the repo).',
          false
        );
        try {
          renderExternals(data);
          renderPeerLme(data);
          buildCharts(data);
        } catch (e) {
          setStatus(
            statusEl,
            'Chart render failed: ' + (e && e.message ? e.message : String(e)),
            true
          );
          setGridLoading(false, true);
          return;
        }
        setGridLoading(false, false);
      })
      .catch(function (err) {
        setGridLoading(false, true);
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
