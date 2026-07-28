/* global d3, marked, DOMPurify */
(async () => {
  /* ── Helpers ─────────────────────────────────────────────────────── */
  function esc(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === "text") node.textContent = attrs[k];
      else if (k === "cls") node.className = attrs[k];
      else if (k === "style") node.setAttribute("style", attrs[k]);
      else if (k === "onclick") node.addEventListener("click", attrs[k]);
      else node.setAttribute(k, attrs[k]);
    });
    if (children) children.forEach(function (c) { if (c) node.appendChild(c); });
    return node;
  }

  function svgEl(tag, attrs) {
    var node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    if (attrs) Object.keys(attrs).forEach(function (k) { node.setAttribute(k, attrs[k]); });
    return node;
  }

  /* ── Load data ───────────────────────────────────────────────────── */
  var res = await fetch("wiki-data.json");
  if (!res.ok) {
    var emptyEl = document.getElementById("reader-empty");
    emptyEl.textContent = "";
    emptyEl.appendChild(el("p", { text: "Missing wiki-data.json — run: llm-wiki build-site", style: "color:var(--muted)" }));
    return;
  }
  var data = await res.json();
  var meta = data.meta || {};
  var pname = meta.personaName || "Gennie";

  document.title = pname + " · wiki";
  document.getElementById("persona-name").textContent = pname;

  var nodes = (data.nodes || []).map(function (n) { return Object.assign({}, n); });
  if (!nodes.length) {
    document.getElementById("reader-empty").querySelector("p").textContent =
      "No wiki pages yet. Add markdown to wiki/ and rebuild.";
    return;
  }

  var nodeById = {};
  nodes.forEach(function (n) { nodeById[n.id] = n; });

  var rawEdges = data.edges || [];
  var simLinks = rawEdges
    .map(function (e) {
      var s = nodeById[e.source], t = nodeById[e.target];
      return s && t ? { source: s, target: t } : null;
    })
    .filter(Boolean);

  nodes.forEach(function (n) { n.degree = 0; });
  simLinks.forEach(function (l) { l.source.degree++; l.target.degree++; });

  function dirOf(path) { var i = path.lastIndexOf("/"); return i > 0 ? path.slice(0, i) : ""; }
  var dirs = Array.from(new Set(nodes.map(function (n) { return dirOf(n.path); }))).sort();
  var palette = ["#38bdf8", "#a78bfa", "#7dd3fc", "#c4b5fd", "#22d3ee", "#818cf8", "#67e8f9", "#ddd6fe", "#38bdf8"];
  var dirColor = {};
  dirs.forEach(function (d, i) { dirColor[d] = palette[i % palette.length]; });
  function colorOf(n) { return dirColor[dirOf(n.path)] || palette[0]; }

  var neighborIds = {};
  nodes.forEach(function (n) { neighborIds[n.id] = new Set(); });
  simLinks.forEach(function (l) {
    neighborIds[l.source.id].add(l.target.id);
    neighborIds[l.target.id].add(l.source.id);
  });

  var selectedNode = null;

  function absoluteWikiPath(relPath) {
    var root = meta.vaultAbsolutePath || "";
    return root ? root.replace(/\/$/, "") + "/wiki/" + relPath : "";
  }

  function openFileHref(absPath) {
    if (!absPath) return "#";
    var scheme = meta.openFileScheme || "file";
    if (scheme === "vscode") return "vscode://file" + absPath;
    if (scheme === "cursor") return "cursor://file" + absPath;
    return "file://" + absPath;
  }

  /* ── File tree ───────────────────────────────────────────────────── */
  (function buildTree() {
    var treeEl = document.getElementById("file-tree");
    var groups = {};
    nodes.forEach(function (n) {
      var dir = dirOf(n.path);
      (groups[dir] || (groups[dir] = [])).push(n);
    });

    Object.keys(groups)
      .sort(function (a, b) { return !a ? -1 : !b ? 1 : a.localeCompare(b); })
      .forEach(function (dir) {
        var g = el("div", { cls: "tree-group" });

        if (dir) {
          var chevronSvg = svgEl("svg", { class: "tree-group-chevron", viewBox: "0 0 12 12", fill: "none", stroke: "currentColor", "stroke-width": "1.5", "stroke-linecap": "round" });
          chevronSvg.appendChild(svgEl("path", { d: "M4 2l4 4-4 4" }));

          var folderLabels = meta.folderLabels || {};
          var friendlyName = folderLabels[dir] || dir.replace(/[-_]/g, " ").replace(/\b\w/g, function (c) { return c.toUpperCase(); })
            .replace(/\bAi\s*Ml\b/gi, "AI/ML").replace(/\bAi\b/g, "AI").replace(/\bMl\b/g, "ML")
            .replace(/\bLlm\b/g, "LLM").replace(/\bApi\b/g, "API").replace(/\bNlp\b/g, "NLP");
          var folderSvg = svgEl("svg", { class: "tree-folder-icon", viewBox: "0 0 16 16", fill: "currentColor" });
          folderSvg.appendChild(svgEl("path", { d: "M1.5 2A1.5 1.5 0 0 0 0 3.5v9A1.5 1.5 0 0 0 1.5 14h13a1.5 1.5 0 0 0 1.5-1.5V5.5A1.5 1.5 0 0 0 14.5 4H7.414a1 1 0 0 1-.707-.293L5.854 2.854A2 2 0 0 0 4.44 2.1z" }));
          var lbl = el("button", {
            cls: "tree-group-label",
            type: "button",
            "aria-expanded": "true",
            onclick: function () {
              var collapsed = g.classList.toggle("collapsed");
              lbl.setAttribute("aria-expanded", String(!collapsed));
            }
          }, [
            chevronSvg,
            folderSvg,
            el("span", { text: friendlyName })
          ]);
          g.appendChild(lbl);
        }

        var items = el("div", { cls: "tree-group-items" });
        groups[dir]
          .sort(function (a, b) { return a.title.localeCompare(b.title); })
          .forEach(function (n) {
            var dot = el("span", { cls: "tree-dot", style: "background:" + colorOf(n) });
            var txt = el("span", { cls: "tree-item-text", text: n.title });
            var item = el("button", {
              cls: "tree-item",
              type: "button",
              "data-id": n.id,
              onclick: function () { selectNode(n); }
            }, [dot, txt]);
            items.appendChild(item);
          });
        g.appendChild(items);
        treeEl.appendChild(g);
      });
  })();

  /* ── D3 Graph ────────────────────────────────────────────────────── */
  var graphPane = document.getElementById("graph-pane");
  var svg = d3.select("#graph-svg");
  function w() { return graphPane.clientWidth || 800; }
  function h() { return graphPane.clientHeight || 600; }
  svg.attr("viewBox", [0, 0, w(), h()]);

  var gRoot = svg.append("g");

  var sim = d3
    .forceSimulation(nodes)
    .force("link", d3.forceLink(simLinks).id(function (d) { return d.id; }).distance(55))
    .force("charge", d3.forceManyBody().strength(-100))
    .force("center", d3.forceCenter(w() / 2, h() / 2))
    .force("collision", d3.forceCollide().radius(function (d) { return nodeR(d) + 3; }));

  function nodeR(d) { return 5 + Math.min(11, (d.degree || 0) * 0.8); }

  var linkSel = gRoot.append("g").selectAll("line").data(simLinks).join("line").attr("class", "edge-line");

  var nodeSel = gRoot
    .append("g")
    .selectAll("g")
    .data(nodes)
    .join("g")
    .call(
      d3.drag()
        .on("start", function (ev, d) { if (!ev.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
        .on("drag", function (ev, d) { d.fx = ev.x; d.fy = ev.y; })
        .on("end", function (ev, d) { if (!ev.active) sim.alphaTarget(0); d.fx = null; d.fy = null; })
    )
    .on("click", function (ev, d) { selectNode(d); })
    .on("mouseenter", function (ev, d) { highlightNeighbors(d); })
    .on("mouseleave", clearHighlight);

  var circles = nodeSel.append("circle").attr("class", "node-circle").attr("r", nodeR).attr("fill", colorOf);
  var lbls = nodeSel
    .append("text")
    .attr("class", "node-label")
    .attr("dx", function (d) { return nodeR(d) + 4; })
    .attr("dy", 3)
    .text(function (d) { return d.title.length > 22 ? d.title.slice(0, 20) + "…" : d.title; });

  sim.on("tick", function () {
    linkSel
      .attr("x1", function (l) { return l.source.x; }).attr("y1", function (l) { return l.source.y; })
      .attr("x2", function (l) { return l.target.x; }).attr("y2", function (l) { return l.target.y; });
    nodeSel.attr("transform", function (d) { return "translate(" + d.x + "," + d.y + ")"; });
  });

  svg.call(d3.zoom().scaleExtent([0.15, 5]).on("zoom", function (ev) { gRoot.attr("transform", ev.transform); }));

  window.addEventListener("resize", function () {
    svg.attr("viewBox", [0, 0, w(), h()]);
    sim.force("center", d3.forceCenter(w() / 2, h() / 2));
    sim.alpha(0.3).restart();
  });

  document.getElementById("graph-stats").textContent = nodes.length + " pages · " + simLinks.length + " links";

  /* ── Graph highlight ─────────────────────────────────────────────── */
  function highlightNeighbors(d) {
    var nbs = neighborIds[d.id];
    circles.classed("dimmed", function (n) { return n.id !== d.id && !nbs.has(n.id); });
    lbls.classed("dimmed", function (n) { return n.id !== d.id && !nbs.has(n.id); });
    linkSel.classed("dimmed", function (l) { return l.source.id !== d.id && l.target.id !== d.id; });
    linkSel.classed("highlighted", function (l) { return l.source.id === d.id || l.target.id === d.id; });
    circles.filter(function (n) { return n.id === d.id; }).classed("hovered", true);
  }

  function clearHighlight() {
    circles.classed("dimmed", false).classed("hovered", false);
    lbls.classed("dimmed", false);
    linkSel.classed("dimmed", false).classed("highlighted", false);
  }

  /* ── Select node ─────────────────────────────────────────────────── */
  function selectNode(d) {
    selectedNode = d;
    document.querySelectorAll(".tree-item").forEach(function (item) {
      item.classList.toggle("active", item.getAttribute("data-id") === d.id);
    });
    circles.classed("selected", function (n) { return n.id === d.id; });
    showReader(d);
  }

  /* ── Reader ──────────────────────────────────────────────────────── */
  function showReader(d) {
    document.getElementById("reader-empty").style.display = "none";
    var scroll = document.getElementById("reader-scroll");
    scroll.style.display = "";

    var abs = absoluteWikiPath(d.path);
    var scheme = meta.openFileScheme || "file";
    var href = openFileHref(abs);

    var seen = {};
    var uniqueLinked = rawEdges
      .filter(function (e) { return e.source === d.id || e.target === d.id; })
      .map(function (e) { return e.source === d.id ? e.target : e.source; })
      .filter(function (id) { return nodeById[id] && !seen[id] && (seen[id] = true); })
      .map(function (id) { return nodeById[id]; });

    /* Reader header */
    var hdr = document.getElementById("reader-header");
    hdr.textContent = "";
    hdr.appendChild(el("div", { cls: "reader-title", text: d.title }));

    var metaRow = el("div", { cls: "reader-meta" });
    var today = new Date().toISOString().slice(0, 10);
    metaRow.appendChild(el("span", { text: "Last updated: " + today }));
    metaRow.appendChild(el("span", { cls: "dot", text: "·" }));
    metaRow.appendChild(el("span", { text: uniqueLinked.length + " link" + (uniqueLinked.length !== 1 ? "s" : "") }));
    if (abs) {
      metaRow.appendChild(el("span", { cls: "dot", text: "·" }));
      metaRow.appendChild(el("a", { cls: "open-file-link", href: href, text: "Open in " + scheme }));
    }
    hdr.appendChild(metaRow);

    /* Markdown body — only place we use sanitized HTML rendering */
    var md = d.markdown || "";
    if (md.startsWith("---")) {
      var fmEnd = md.indexOf("\n---", 3);
      if (fmEnd !== -1) md = md.slice(fmEnd + 4).trimStart();
    }
    md = md.replace(/^#\s+.+\n+/, "");
    var dirty = marked.parse(md);
    var clean = typeof DOMPurify !== "undefined" ? DOMPurify.sanitize(dirty) : dirty;
    var bodyEl = document.getElementById("reader-body");
    var safeContainer = document.createElement("div");
    safeContainer.appendChild(DOMPurify.sanitize(dirty, { RETURN_DOM_FRAGMENT: true }));
    bodyEl.textContent = "";
    bodyEl.appendChild(safeContainer);

    /* Linked pages */
    var section = document.getElementById("linked-section");
    section.textContent = "";
    if (uniqueLinked.length) {
      section.appendChild(el("div", { cls: "linked-heading", text: "Linked pages" }));
      var cards = el("div", { cls: "linked-cards" });
      uniqueLinked.forEach(function (n) {
        var c = colorOf(n);
        var colorBar = el("div", { cls: "linked-card-color", style: "background:linear-gradient(135deg, " + c + "22 0%, #0f162988 40%, " + c + "33 100%), radial-gradient(circle at 30% 60%, " + c + "44, transparent 60%), var(--bg-surface)" });
        var title = el("div", { cls: "linked-card-title", text: n.title });
        var path = el("div", { cls: "linked-card-path", text: n.path });
        var card = el("div", { cls: "linked-card", "data-id": n.id, onclick: function () { selectNode(n); } }, [colorBar, title, path]);
        cards.appendChild(card);
      });
      section.appendChild(cards);
    }
    scroll.scrollTop = 0;
  }

  /* ── Ledger (activity strip: date + tag + short title, readable wrap) ─ */
  (function renderLedger() {
    var ledgerEl = document.getElementById("app-ledger");
    var entries = data.ledger || [];
    if (!entries.length) { ledgerEl.classList.add("empty"); return; }
    var dotSizes = [12, 8, 10, 7, 11, 9, 8, 10, 7, 12];
    entries.forEach(function (c, i) {
      var sz = dotSizes[i % dotSizes.length];
      var dot = el("span", { cls: "ledger-dot", style: "width:" + sz + "px;height:" + sz + "px" });
      var subject = String(c.subject || "");
      var tag = null;
      var title = subject;
      var m = subject.match(/^\[([^\]]+)\]\s*(.*)$/);
      if (m) {
        tag = m[1];
        title = (m[2] || "").trim() || tag;
      }
      var meta = el("div", { cls: "ledger-meta" });
      meta.appendChild(el("time", { cls: "ledger-date", datetime: c.date, text: c.date }));
      if (tag) meta.appendChild(el("span", { cls: "ledger-tag", text: tag }));
      var subj = el("p", { cls: "ledger-subject", text: title });
      subj.setAttribute("title", subject);
      var body = el("div", { cls: "ledger-body" }, [meta, subj]);
      ledgerEl.appendChild(el("div", { cls: "ledger-entry" }, [dot, body]));
    });
  })();

  /* ── Search ──────────────────────────────────────────────────────── */
  (function initSearch() {
    var input = document.getElementById("search-input");
    document.addEventListener("keydown", function (e) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        input.focus();
        input.select();
      }
      if (e.key === "Escape" && document.activeElement === input) {
        input.value = "";
        applyFilter("");
        input.blur();
      }
    });
    input.addEventListener("input", function () { applyFilter(input.value); });

    function applyFilter(q) {
      var lower = q.toLowerCase().trim();
      var matches = new Set();
      if (lower) {
        nodes.forEach(function (n) {
          if (n.title.toLowerCase().indexOf(lower) !== -1 || n.path.toLowerCase().indexOf(lower) !== -1)
            matches.add(n.id);
        });
      }
      document.querySelectorAll(".tree-item").forEach(function (item) {
        item.style.display = !lower || matches.has(item.getAttribute("data-id")) ? "" : "none";
      });
      if (lower) {
        circles.classed("dimmed", function (n) { return !matches.has(n.id); });
        lbls.classed("dimmed", function (n) { return !matches.has(n.id); });
        linkSel.classed("dimmed", function (l) { return !matches.has(l.source.id) && !matches.has(l.target.id); });
      } else {
        circles.classed("dimmed", false);
        lbls.classed("dimmed", false);
        linkSel.classed("dimmed", false);
      }
    }
  })();

  /* ── Sidebar toggle ──────────────────────────────────────────────── */
  document.getElementById("toggle-sidebar").addEventListener("click", function () {
    var sidebar = document.getElementById("sidebar");
    var collapsed = sidebar.classList.toggle("collapsed");
    this.setAttribute("aria-expanded", String(!collapsed));
  });
})();
