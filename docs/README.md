# GitHub Pages (this folder)

**Quickstart (vault path + tiers):** [`QUICKSTART.md`](./QUICKSTART.md). **Environment variables:** [`ENV.md`](./ENV.md). **Pages design tokens (GitHub Pages UI):** [`DESIGN.md`](./DESIGN.md). **Publishing checklist:** [`PUBLISHING.md`](./PUBLISHING.md). **Optional demo asset note:** [`DEMO.md`](./DEMO.md).

Static site for **llm-wiki**: Inspiration (Karpathy gist, MemPalace, Newton quote), goal, setup (Claude Code, Cursor, Codex/others, Obsidian), clone & dev, vault workflow. **Landing page assets** live under **`site/`** (same idea as **`memory/`** — markdown docs stay at `docs/*.md` without mixing HTML/CSS bundles at the top level). Design tokens and component notes: **[`DESIGN.md`](./DESIGN.md)**.

**Published home page:** GitHub Pages uses this **`docs/`** folder as the site root. **`docs/index.html`** redirects (with hash preserved) to **`site/index.html`**. Users still open `https://<org>.github.io/<repo>/` — the root page forwards to the landing bundle. A duplicate **`docs/favicon.ico`** sits at the repo root of `docs/` so bare requests to `/favicon.ico` resolve.

**No Jekyll:** The empty **`docs/.nojekyll`** file tells GitHub Pages not to run Jekyll, so static assets (HTML, CSS, paths starting with `_`, etc.) are served as-is.

## Enable Pages

1. Repo **Settings → Pages**
2. **Build and deployment**: Source = **Deploy from a branch**
3. Branch = **`main`** (or your default), folder = **`/docs`**
4. Save. The site URL will be `https://<org>.github.io/<repo>/` (root `index.html` redirects into **`site/`**).

If the site 404s, wait a minute and hard-refresh.

## Edit

- **`index.html`** (root) — tiny redirect into **`site/`** (preserves `#fragment` via JavaScript)
- **`site/index.html`** — landing page structure and copy
- **`memory/index.html`** — Memory & retrieval hub (session memory, MCP search, benchmark doc links, Chart.js dashboard); served at `/memory/` and `/memory/index.html` on Pages
- **`memory/metrics-dashboard.json`** — numbers for the hub charts (commit when serious benchmark runs land; keep aligned with `memory/benchmarks/comparisons.md`)
- **`memory/metrics-dashboard.js`** — loads the JSON and renders charts (Chart.js from CDN)
- **`site/css/style.css`** — layout and theme (shared with **`memory/index.html`**)
- **`site/assets/logo.png`** — wide header logo (natural aspect)
- **`site/assets/logo-square.png`** — square canvas (same art, padded to 1:1); source for regenerating favicons
- **`site/favicon.ico`**, **`site/favicon-16x16.png`**, **`site/favicon-32x32.png`**, **`site/apple-touch-icon.png`** — linked from **`site/index.html`**; **`favicon.ico`** is also copied at **`docs/favicon.ico`** for default browser probes; rebuild from `logo-square.png` when the logo changes (e.g. Pillow resizing + ICO bundle)
