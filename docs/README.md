# GitHub Pages (`docs/`)

This folder is the **published site** when you enable GitHub Pages from the repo’s **`/docs`** directory.

**Start here**

- **[`INSTALL.md`](./INSTALL.md)** — Claude Code install, `/reload-plugins`, slash-first steps, dev clone  
- **[`QUICKSTART.md`](./QUICKSTART.md)** — vault vs plugin repo, five-minute setup, capability tiers  
- **[`INSPIRATION.md`](./INSPIRATION.md)** — credits and lineage  
- **[`CLI.md`](./CLI.md)** — `llm-wiki` CLI entrypoint and subcommands  
- **[`CONFIGURATION.md`](./CONFIGURATION.md)** — `config.json` reference  
- **[`ENV.md`](./ENV.md)** — environment variables  
- **[`PUBLISHING.md`](./PUBLISHING.md)** — enable Pages, marketplace smoke tests  

**What gets served**

- **`index.html`** at the site root — marketing landing (plugin overview, install hints, links to the memory hub).  
- **`css/style.css`** — shared styles for the landing and **[`memory/index.html`](./memory/index.html)** (design tokens: typography, colors, layout).  
- **`assets/`** — logos and images used by the HTML pages.  
- **`memory/`** — Memory & retrieval hub (charts, doc links). Markdown references such as **`AGENTS.shared.md`** live next to these files for GitHub browsing, not for the static HTML bundle.

**Behavior**

GitHub Pages uses **`docs/`** as the web root. There is **no** extra redirect: opening `https://<org>.github.io/<repo>/` serves **`index.html`**. **`favicon.ico`** is at the root of **`docs/`** so `/favicon.ico` resolves.

**Jekyll:** Keep an empty **`docs/.nojekyll`** file so GitHub Pages does not run Jekyll (static files and paths starting with `_` are served as-is).

---

## Enable Pages

1. Repo **Settings → Pages**  
2. **Build and deployment:** **Deploy from a branch**  
3. Branch: **`main`** (or your default), folder: **`/docs`**  
4. Save. The site URL is `https://<org>.github.io/<repo>/`

If you see a 404, wait a minute and hard-refresh.

---

## Editing the static site

| Path | Role |
|------|------|
| **`index.html`** | Landing page markup |
| **`css/style.css`** | Styles (shared with **`memory/index.html`**) |
| **`assets/`** | **`logo.png`**, **`logo-square.png`**, **`readme-banner.png`**, **`logo-mark.svg`** |
| **`favicon.ico`**, **`favicon-16x16.png`**, **`favicon-32x32.png`**, **`apple-touch-icon.png`** | Icons linked from **`index.html`**; regenerate from **`assets/logo-square.png`** when the brand asset changes |
| **`memory/index.html`** | Memory & retrieval hub |
| **`memory/metrics-dashboard.json`** | Data for hub charts (update when you publish serious benchmark numbers; keep narrative aligned with **[`benchmarks/README.md`](../benchmarks/README.md)**) |
| **`memory/metrics-dashboard.js`** | Loads the JSON and draws charts (Chart.js from a CDN) |
