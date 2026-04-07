# Static wiki viewer assets

Pinned CDNs (update intentionally):

- Tailwind Play: `https://cdn.tailwindcss.com`
- D3 v7: `https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js`
- marked: `https://cdn.jsdelivr.net/npm/marked/marked.min.js`
- DOMPurify 3.2.4: `https://cdn.jsdelivr.net/npm/dompurify@3.2.4/dist/purify.min.js` (sanitizes markdown HTML before `innerHTML`)

Serve `wiki/.og/` with `python3 -m http.server` so `fetch('wiki-data.json')` works.
