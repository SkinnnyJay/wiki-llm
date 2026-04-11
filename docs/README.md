<p align="center">
  <img src="assets/readme-banner.png" alt="llm-wiki" width="100%" />
</p>

<p align="center">
  <a href="https://github.com/SkinnnyJay/wiki-llm"><img src="https://img.shields.io/badge/GitHub-repo-181717?logo=github&logoColor=white" alt="GitHub repository"/></a>
  <a href="https://github.com/SkinnnyJay/wiki-llm#install-claude-code"><img src="https://img.shields.io/badge/Claude%20Code-plugin-D4A574?logo=anthropic&logoColor=white" alt="Claude Code: install instructions"/></a>
  <a href="https://github.com/SkinnnyJay/wiki-llm/blob/main/AGENTS.md"><img src="https://img.shields.io/badge/Cursor-rules%20%2B%20plugin-000000?logo=cursor&logoColor=white" alt="Cursor: AGENTS.md"/></a>
</p>


# GitHub Pages (`docs/`)

This folder is the **published site** when you enable GitHub Pages from the repo’s **`/docs`** directory.

**Doc convention (throughout `docs/`):** **Claude Code** (slash commands + skills) first, then the **`llm-wiki`** **CLI**, then **bash / shell** for scripts and automation.

**Start here**

- **[`INSTALL.md`](./INSTALL.md)** — install order: Claude Code → CLI → bash examples  
- **[`SLASH-COMMANDS.md`](./SLASH-COMMANDS.md)** — every **`/llm-wiki:…`** command, summaries, links to [`commands/`](../commands/) and CLI  
- **[`QUICKSTART.md`](./QUICKSTART.md)** — five-minute path with the same order  
- **[`INSPIRATION.md`](./INSPIRATION.md)** — credits, lineage, feature survey (Claude → CLI → bash)  
- **[`CLI.md`](./CLI.md)** — CLI reference + slash → CLI map  
- **[`CONFIGURATION.md`](./CONFIGURATION.md)** — `/llm-wiki:configure`, `llm-wiki configure -i`, then `config.json`  
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
