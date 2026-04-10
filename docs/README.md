# GitHub Pages (this folder)

**Quickstart (vault path + tiers):** [`QUICKSTART.md`](./QUICKSTART.md). **Publishing checklist:** [`PUBLISHING.md`](./PUBLISHING.md). **Optional demo asset note:** [`DEMO.md`](./DEMO.md).

Static site for **llm-wiki**: Inspiration (Karpathy gist, MemPalace, Newton quote), goal, setup (Claude Code, Cursor, Codex/others, Obsidian), clone & dev, vault workflow. Assets: `assets/logo.png` (wide art), `assets/logo-square.png` (square master for raster favicons), `favicon.ico` + `favicon-16x16.png` / `favicon-32x32.png` + `apple-touch-icon.png`, `css/style.css`.

**Published home page:** GitHub Pages uses this **`docs/`** folder as the site root. The landing page is **`index.html`** — it is served at `https://<org>.github.io/<repo>/` and `https://<org>.github.io/<repo>/index.html`.

**No Jekyll:** The empty **`docs/.nojekyll`** file tells GitHub Pages not to run Jekyll, so static assets (HTML, CSS, paths starting with `_`, etc.) are served as-is.

## Enable Pages

1. Repo **Settings → Pages**
2. **Build and deployment**: Source = **Deploy from a branch**
3. Branch = **`main`** (or your default), folder = **`/docs`**
4. Save. The site URL will be `https://<org>.github.io/<repo>/` (same as **`index.html`**).

If the site 404s, wait a minute and hard-refresh.

## Edit

- **`index.html`** — page structure and copy
- **`memory/index.html`** — Memory & retrieval hub (session memory, MCP search, benchmark doc links, Chart.js dashboard); served at `/memory/` and `/memory/index.html` on Pages
- **`memory/metrics-dashboard.json`** — numbers for the hub charts (commit when serious benchmark runs land; keep aligned with `memory/benchmarks/comparisons.md`)
- **`memory/metrics-dashboard.js`** — loads the JSON and renders charts (Chart.js from CDN)
- **`css/style.css`** — layout and theme
- **`assets/logo.png`** — wide header logo (natural aspect)
- **`assets/logo-square.png`** — square canvas (same art, padded to 1:1); source for regenerating favicons
- **`favicon.ico`**, **`favicon-16x16.png`**, **`favicon-32x32.png`**, **`apple-touch-icon.png`** — linked from `index.html`; rebuild from `logo-square.png` when the logo changes (e.g. Pillow resizing + ICO bundle)
