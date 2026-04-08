# Static wiki viewer assets

Three-column layout: page tree · D3 force graph · markdown reader.

## CDN dependencies (update intentionally)

- **D3 v7:** `https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js`
- **marked v17:** `https://cdn.jsdelivr.net/npm/marked@17/marked.min.js`
- **DOMPurify 3.2.4:** `https://cdn.jsdelivr.net/npm/dompurify@3.2.4/dist/purify.min.js` (sanitizes markdown HTML via `RETURN_DOM_FRAGMENT`)
- **Google Fonts:** DM Sans (UI) + Source Serif 4 (reader body) — matching `docs/css/style.css`

Tailwind CDN was removed in favor of custom CSS with design tokens from `docs/css/style.css`.

## Serving

`llm-wiki build-site` writes `wiki-data.json` + these assets to `wiki/.og/`.

```sh
cd llm-wiki/wiki/.og && python3 -m http.server 8765
```

Open `http://127.0.0.1:8765/` — serve over HTTP, not `file://`, so `fetch()` works.

## Features

- **Folder tree** — pages grouped by directory, collapsible groups
- **Search** — `⌘K` to focus; filters tree + dims graph nodes in real time
- **Graph** — D3 force layout, nodes colored by directory, sized by degree; hover highlights neighbors, click opens reader
- **Reader** — serif title, metadata bar, rendered markdown with code blocks / blockquotes / tables, linked-page cards
- **Ledger** — horizontal git timeline strip at bottom (when vault git is enabled)
- **Sidebar toggle** — collapse page tree for more graph space
- **Responsive** — sidebar hides at 900px, stacks vertically at 640px
