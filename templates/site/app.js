/* global d3, marked, DOMPurify */
(async () => {
  const res = await fetch("wiki-data.json");
  if (!res.ok) {
    document.getElementById("reader").innerHTML = "<p>Missing wiki-data.json — run <code>llm-wiki build-site</code></p>";
    return;
  }
  const data = await res.json();
  const meta = data.meta || {};
  const pname = meta.personaName || "Gennie";
  document.title = `${pname} · wiki`;
  const hdr = document.querySelector("header h1");
  if (hdr) hdr.textContent = pname;

  const nodes = data.nodes.map((n) => ({ ...n }));
  const nodeById = Object.fromEntries(nodes.map((n) => [n.id, n]));
  // Object references required for d3.forceLink to resolve endpoints reliably
  const links = (data.edges || [])
    .map((e) => {
      const s = nodeById[e.source];
      const t = nodeById[e.target];
      if (!s || !t) return null;
      return { source: s, target: t };
    })
    .filter(Boolean);

  const ledgerEl = document.getElementById("ledger");
  if (data.ledger && data.ledger.length) {
    ledgerEl.classList.remove("hidden");
    ledgerEl.innerHTML =
      "<div class='font-semibold text-slate-300 mb-1'>Vault git (recent)</div>" +
      data.ledger
        .map((c) => `<div>${escapeHtml(c.date)} — ${escapeHtml(c.subject)}</div>`)
        .join("");
  }

  const graphPane = document.getElementById("graph-pane");
  const reader = document.getElementById("reader");
  const width = graphPane.clientWidth || 800;
  const height = graphPane.clientHeight || 600;
  const svg = d3.select("#graph").attr("viewBox", [0, 0, width, height]);
  const g = svg.append("g");

  const sim = d3
    .forceSimulation(nodes)
    .force(
      "link",
      d3
        .forceLink(links)
        .id((d) => d.id)
        .distance(80)
    )
    .force("charge", d3.forceManyBody().strength(-120))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force("collision", d3.forceCollide().radius(28));

  const link = g
    .append("g")
    .attr("class", "links")
    .selectAll("line")
    .data(links)
    .join("line")
    .attr("class", "link");

  const node = g
    .append("g")
    .attr("class", "nodes")
    .selectAll("g")
    .data(nodes)
    .join("g")
    .attr("class", "node")
    .call(
      d3
        .drag()
        .on("start", (ev, d) => {
          if (!ev.active) sim.alphaTarget(0.3).restart();
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
    .on("click", (ev, d) => showNode(d));

  node.append("circle").attr("r", 10);
  node
    .append("text")
    .attr("dx", 14)
    .attr("dy", 4)
    .text((d) => d.title.slice(0, 24) + (d.title.length > 24 ? "…" : ""));

  sim.on("tick", () => {
    link
      .attr("x1", (d) => d.source.x)
      .attr("y1", (d) => d.source.y)
      .attr("x2", (d) => d.target.x)
      .attr("y2", (d) => d.target.y);
    node.attr("transform", (d) => `translate(${d.x},${d.y})`);
  });

  function absoluteWikiPath(relPath) {
    const root = (data.meta && data.meta.vaultAbsolutePath) || "";
    if (!root) return "";
    const sep = root.endsWith("/") ? "" : "/";
    return `${root}${sep}wiki/${relPath}`;
  }

  function openFileHref(absPath) {
    if (!absPath) return "#";
    const scheme = (data.meta && data.meta.openFileScheme) || "file";
    if (scheme === "vscode") return "vscode://file" + absPath;
    if (scheme === "cursor") return "cursor://file" + absPath;
    return "file://" + absPath;
  }

  function showNode(d) {
    const dirty = marked.parse(d.markdown || "");
    const html = typeof DOMPurify !== "undefined" ? DOMPurify.sanitize(dirty) : dirty;
    const neighbors = (data.edges || [])
      .filter((e) => e.source === d.id || e.target === d.id)
      .map((e) => {
        const o = e.source === d.id ? e.target : e.source;
        const n = nodeById[o];
        return n ? n.title : o;
      });
    const abs = absoluteWikiPath(d.path);
    const openBtn = abs
      ? `<a class="inline-block mt-2 text-sky-400 hover:underline text-sm" href="${escapeHtml(
          openFileHref(abs)
        )}">Open file (${escapeHtml((data.meta && data.meta.openFileScheme) || "file")})</a>
       <p class="text-xs text-slate-600 mt-1 break-all">${escapeHtml(abs)}</p>`
      : "";
    reader.innerHTML = `
      <h2 class="text-xl font-bold text-sky-300">${escapeHtml(d.title)}</h2>
      <p class="text-xs text-slate-500 mb-2">${escapeHtml(d.path)}</p>
      ${openBtn}
      <div class="text-sm text-slate-400 mb-3 mt-3">Linked: ${neighbors.map(escapeHtml).join(", ") || "—"}</div>
      <div class="markdown-body">${html}</div>
    `;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  svg.call(
    d3.zoom().on("zoom", (ev) => {
      g.attr("transform", ev.transform);
    })
  );
})();
