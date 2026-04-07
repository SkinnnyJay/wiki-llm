# GitHub Pages (this folder)

Static site for **llm-wiki**: Inspiration (Karpathy gist + Newton quote), goal, setup (Claude Code, Cursor, Codex/others, Obsidian), clone & dev, vault workflow. Assets: `assets/logo.png` (wide art), `assets/logo-square.png` (square master for raster favicons), `favicon.ico` + `favicon-16x16.png` / `favicon-32x32.png` + `apple-touch-icon.png`, `css/style.css`.

## Enable Pages

1. Repo **Settings → Pages**
2. **Build and deployment**: Source = **Deploy from a branch**
3. Branch = **`main`** (or your default), folder = **`/docs`**
4. Save. Site URL will look like `https://<org>.github.io/<repo>/`

If the site 404s, wait a minute and hard-refresh. No Jekyll: empty **`docs/.nojekyll`** is present.

## Edit

- **`index.html`** — page structure and copy
- **`css/style.css`** — layout and theme
- **`assets/logo.png`** — wide header logo (natural aspect)
- **`assets/logo-square.png`** — square canvas (same art, padded to 1:1); source for regenerating favicons
- **`favicon.ico`**, **`favicon-16x16.png`**, **`favicon-32x32.png`**, **`apple-touch-icon.png`** — linked from `index.html`; rebuild from `logo-square.png` when the logo changes (e.g. Pillow resizing + ICO bundle)
