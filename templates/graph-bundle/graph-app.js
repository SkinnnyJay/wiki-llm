/* global d3 */
(async () => {
  const res = await fetch("graph-data.json");
  if (!res.ok) {
    document.getElementById("detail").textContent = "Missing graph-data.json — run llm-wiki graph";
    return;
  }
  const data = await res.json();
  const meta = data.meta || {};
  const mode = meta.mode || "links";
  const pname = meta.persona_name || "Gennie";

  document.title = `${pname} · graph`;
  document.getElementById("graph-title").textContent = `${pname} — ${meta.title || "Wiki graph"}`;

  const nodes = (data.nodes || []).map((n) => ({ ...n }));
  if (!nodes.length) {
    document.getElementById("graph-sub").textContent = "No wiki pages under llm-wiki/wiki/";
    document.getElementById("detail").textContent = "Add markdown pages, then re-run llm-wiki graph.";
    return;
  }

  document.getElementById("graph-sub").textContent = `${meta.node_count ?? 0} pages · ${meta.edge_count ?? 0} links · ${mode}`;

  const nodeById = Object.fromEntries(nodes.map((n) => [n.id, n]));
  const links = (data.edges || [])
    .map((e) => {
      const s = nodeById[e.source];
      const t = nodeById[e.target];
      if (!s || !t) return null;
      return { source: s, target: t };
    })
    .filter(Boolean);

  const palette = d3.schemeTableau10;
  const clusterCount = Math.max(1, (data.clusters || []).length || 1);

  function nodeColor(d) {
    if (mode === "knowledge" && clusterCount > 1) {
      return palette[d.cluster % palette.length];
    }
    const t = d3.scaleSequential(d3.interpolateBlues).domain([0, d3.max(nodes, (x) => x.degree) || 1]);
    return t(d.degree || 0);
  }

  const legend = document.getElementById("legend");
  const legendItems = document.getElementById("legend-items");
  if (mode === "knowledge" && (data.clusters || []).length > 1) {
    legend.classList.remove("hidden");
    data.clusters.forEach((c) => {
      const color = palette[c.id % palette.length];
      const el = document.createElement("div");
      el.className = "flex gap-2 items-start";
      el.innerHTML = `<span class="w-3 h-3 rounded-full shrink-0 mt-0.5" style="background:${color}"></span><span><span class="text-fg">#${c.id}</span> · ${c.size} pages<br/><span class="opacity-80">${escapeHtml(c.sample_title || "").slice(0, 42)}</span></span>`;
      legendItems.appendChild(el);
    });
  }

  const wrap = document.querySelector(".flex-1.relative");
  const svg = d3.select("#graph-svg");
  const width = () => wrap.clientWidth || 800;
  const height = () => wrap.clientHeight || 600;

  function resize() {
    svg.attr("viewBox", [0, 0, width(), height()]);
    sim.force("center", d3.forceCenter(width() / 2, height() / 2));
    sim.alpha(0.35).restart();
  }

  const sim = d3
    .forceSimulation(nodes)
    .force(
      "link",
      d3
        .forceLink(links)
        .id((d) => d.id)
        .distance((l) => 55 + 8 / (1 + Math.min(l.source.degree || 0, l.target.degree || 0)))
    )
    .force("charge", d3.forceManyBody().strength(-140))
    .force("center", d3.forceCenter(width() / 2, height() / 2))
    .force("collision", d3.forceCollide().radius(22));

  resize();
  window.addEventListener("resize", resize);

  const g = svg.append("g");
  const link = g
    .append("g")
    .attr("class", "links")
    .selectAll("line")
    .data(links)
    .join("line")
    .attr("class", "link-line");

  const node = g
    .append("g")
    .selectAll("g")
    .data(nodes)
    .join("g")
    .call(
      d3
        .drag()
        .on("start", (ev, d) => {
          if (!ev.active) sim.alphaTarget(0.35).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on("drag", (ev, d) => {
          d.fx = ev.x;
          d.fy = ev.y;
        })
        .on("end", (ev, d) => {
          if (!ev.active) sim.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        })
    )
    .on("click", (ev, d) => showDetail(d))
    .on("mousemove", (ev, d) => showTooltip(ev, d))
    .on("mouseleave", hideTooltip);

  node
    .append("circle")
    .attr("class", "node-circle")
    .attr("r", (d) => 6 + Math.min(10, (d.degree || 0) * 0.8))
    .attr("fill", nodeColor);

  node
    .append("text")
    .attr("class", "node-label")
    .attr("dx", 12)
    .attr("dy", 4)
    .text((d) => (d.title || d.id).slice(0, 20) + ((d.title || d.id).length > 20 ? "…" : ""));

  const tooltip = document.getElementById("tooltip");

  function showTooltip(ev, d) {
    tooltip.classList.remove("hidden");
    tooltip.style.left = `${ev.clientX + 12}px`;
    tooltip.style.top = `${ev.clientY + 12}px`;
    const cl = mode === "knowledge" ? `cluster ${d.cluster}` : "links view";
    tooltip.innerHTML = `<strong>${escapeHtml(d.title)}</strong><br/><span class="text-muted">${escapeHtml(d.path)}</span><br/>degree ${d.degree} · ${cl}`;
  }

  function hideTooltip() {
    tooltip.classList.add("hidden");
  }

  function showDetail(d) {
    const nb = (data.edges || [])
      .filter((e) => e.source === d.id || e.target === d.id)
      .map((e) => {
        const o = e.source === d.id ? e.target : e.source;
        const n = nodeById[o];
        return n ? n.title : o;
      });
    document.getElementById("detail").innerHTML = `<div class="text-fg font-medium">${escapeHtml(d.title)}</div>
      <div class="mt-1 break-all opacity-80">${escapeHtml(d.path)}</div>
      <div class="mt-2 text-muted">Linked to (${nb.length}):</div>
      <ul class="mt-1 list-disc pl-4 space-y-0.5">${nb.map((x) => `<li>${escapeHtml(x)}</li>`).join("") || "<li>—</li>"}</ul>`;
  }

  sim.on("tick", () => {
    link
      .attr("x1", (l) => l.source.x)
      .attr("y1", (l) => l.source.y)
      .attr("x2", (l) => l.target.x)
      .attr("y2", (l) => l.target.y);
    node.attr("transform", (d) => `translate(${d.x},${d.y})`);
  });

  svg.call(
    d3.zoom().on("zoom", (ev) => {
      g.attr("transform", ev.transform);
    })
  );

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
})();
