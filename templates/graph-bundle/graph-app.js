/* global d3 */
(async () => {
  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === "text") node.textContent = attrs[k];
      else if (k === "cls") node.className = attrs[k];
      else if (k === "style") node.setAttribute("style", attrs[k]);
      else node.setAttribute(k, attrs[k]);
    });
    if (children) children.forEach(function (c) { if (c) node.appendChild(c); });
    return node;
  }

  function esc(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  var res = await fetch("graph-data.json");
  if (!res.ok) {
    document.getElementById("detail").textContent = "Missing graph-data.json — run llm-wiki graph";
    return;
  }
  var data = await res.json();
  var meta = data.meta || {};
  var mode = meta.mode || "links";
  var pname = meta.persona_name || "Gennie";

  document.title = pname + " · graph";
  document.getElementById("graph-title").textContent = pname + " — " + (meta.title || "Wiki graph");
  document.getElementById("persona-name").textContent = pname;

  var nodes = (data.nodes || []).map(function (n) { return Object.assign({}, n); });
  if (!nodes.length) {
    document.getElementById("graph-sub").textContent = "No wiki pages found.";
    document.getElementById("detail").textContent = "Add markdown pages, then re-run llm-wiki graph.";
    return;
  }

  document.getElementById("graph-meta").textContent =
    (meta.node_count || 0) + " pages · " + (meta.edge_count || 0) + " links · " + mode;

  var nodeById = {};
  nodes.forEach(function (n) { nodeById[n.id] = n; });
  var links = (data.edges || [])
    .map(function (e) {
      var s = nodeById[e.source], t = nodeById[e.target];
      return s && t ? { source: s, target: t } : null;
    })
    .filter(Boolean);

  var palette = d3.schemeTableau10;
  var clusterCount = Math.max(1, (data.clusters || []).length || 1);

  function nodeColor(d) {
    if (mode === "knowledge" && clusterCount > 1) return palette[d.cluster % palette.length];
    var t = d3.scaleSequential(d3.interpolateBlues).domain([0, d3.max(nodes, function (x) { return x.degree; }) || 1]);
    return t(d.degree || 0);
  }

  /* Legend */
  var legend = document.getElementById("legend");
  var legendItems = document.getElementById("legend-items");
  if (mode === "knowledge" && (data.clusters || []).length > 1) {
    legend.classList.remove("hidden");
    data.clusters.forEach(function (c) {
      var color = palette[c.id % palette.length];
      var dot = el("span", { cls: "legend-dot", style: "background:" + color });
      var label = el("span", { cls: "legend-label" });
      label.appendChild(el("strong", { text: "#" + c.id }));
      label.appendChild(document.createTextNode(" · " + c.size + " pages"));
      if (c.sample_title) {
        label.appendChild(el("br"));
        label.appendChild(el("span", { text: c.sample_title.slice(0, 42), style: "opacity:0.8" }));
      }
      legendItems.appendChild(el("div", { cls: "legend-item" }, [dot, label]));
    });
  }

  /* Graph */
  var wrap = document.querySelector(".graph-pane");
  var svg = d3.select("#graph-svg");
  function w() { return wrap.clientWidth || 800; }
  function h() { return wrap.clientHeight || 600; }

  var sim = d3
    .forceSimulation(nodes)
    .force("link", d3.forceLink(links).id(function (d) { return d.id; })
      .distance(function (l) { return 55 + 8 / (1 + Math.min(l.source.degree || 0, l.target.degree || 0)); }))
    .force("charge", d3.forceManyBody().strength(-140))
    .force("center", d3.forceCenter(w() / 2, h() / 2))
    .force("collision", d3.forceCollide().radius(22));

  function resize() {
    svg.attr("viewBox", [0, 0, w(), h()]);
    sim.force("center", d3.forceCenter(w() / 2, h() / 2));
    sim.alpha(0.35).restart();
  }
  resize();
  window.addEventListener("resize", resize);

  var g = svg.append("g");

  var link = g.append("g").selectAll("line").data(links).join("line").attr("class", "link-line");

  var node = g
    .append("g")
    .selectAll("g")
    .data(nodes)
    .join("g")
    .call(
      d3.drag()
        .on("start", function (ev, d) { if (!ev.active) sim.alphaTarget(0.35).restart(); d.fx = d.x; d.fy = d.y; })
        .on("drag", function (ev, d) { d.fx = ev.x; d.fy = ev.y; })
        .on("end", function (ev, d) { if (!ev.active) sim.alphaTarget(0); d.fx = null; d.fy = null; })
    )
    .on("click", function (ev, d) { showDetail(d); })
    .on("mousemove", function (ev, d) { showTooltip(ev, d); })
    .on("mouseleave", hideTooltip);

  node
    .append("circle")
    .attr("class", "node-circle")
    .attr("r", function (d) { return 6 + Math.min(10, (d.degree || 0) * 0.8); })
    .attr("fill", nodeColor);

  node
    .append("text")
    .attr("class", "node-label")
    .attr("dx", 12)
    .attr("dy", 4)
    .text(function (d) { return (d.title || d.id).slice(0, 20) + ((d.title || d.id).length > 20 ? "…" : ""); });

  var tooltip = document.getElementById("tooltip");

  function showTooltip(ev, d) {
    tooltip.classList.remove("hidden");
    tooltip.style.left = (ev.clientX + 12) + "px";
    tooltip.style.top = (ev.clientY + 12) + "px";
    var cl = mode === "knowledge" ? "cluster " + d.cluster : "links view";
    tooltip.textContent = "";
    tooltip.appendChild(el("strong", { text: d.title }));
    tooltip.appendChild(el("br"));
    tooltip.appendChild(el("span", { cls: "tp-muted", text: d.path }));
    tooltip.appendChild(el("br"));
    tooltip.appendChild(document.createTextNode("degree " + d.degree + " · " + cl));
  }

  function hideTooltip() { tooltip.classList.add("hidden"); }

  function showDetail(d) {
    var detailEl = document.getElementById("detail");
    detailEl.textContent = "";
    detailEl.appendChild(el("div", { cls: "detail-node-title", text: d.title }));
    detailEl.appendChild(el("div", { cls: "detail-node-path", text: d.path }));

    var nb = (data.edges || [])
      .filter(function (e) { return e.source === d.id || e.target === d.id; })
      .map(function (e) {
        var o = e.source === d.id ? e.target : e.source;
        var n = nodeById[o];
        return n ? n.title : o;
      });

    var metaText = "Degree: " + d.degree;
    if (mode === "knowledge") metaText += " · Cluster: " + d.cluster;
    detailEl.appendChild(el("div", { cls: "detail-node-meta", text: metaText }));

    detailEl.appendChild(el("div", { cls: "detail-links-label", text: "Linked to (" + nb.length + ")" }));
    var list = el("ul", { cls: "detail-link-list" });
    if (nb.length) {
      nb.forEach(function (t) { list.appendChild(el("li", { text: t })); });
    } else {
      list.appendChild(el("li", { text: "—" }));
    }
    detailEl.appendChild(list);
  }

  sim.on("tick", function () {
    link
      .attr("x1", function (l) { return l.source.x; }).attr("y1", function (l) { return l.source.y; })
      .attr("x2", function (l) { return l.target.x; }).attr("y2", function (l) { return l.target.y; });
    node.attr("transform", function (d) { return "translate(" + d.x + "," + d.y + ")"; });
  });

  svg.call(d3.zoom().scaleExtent([0.15, 5]).on("zoom", function (ev) { g.attr("transform", ev.transform); }));
})();
