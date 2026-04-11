# Publishing — docs site, marketplace, smoke tests

## GitHub Pages (docs site)

1. Repo **Settings → Pages**.
2. **Build and deployment:** Source = **Deploy from a branch**.
3. Branch = **`main`** (or default), folder = **`/docs`**.
4. Ensure **`docs/.nojekyll`** exists so Jekyll does not mangle static files.

After the first deploy, open `https://<org>.github.io/<repo>/` and confirm the root serves **`index.html`** (landing). Details: [`docs/README.md`](./README.md).

## Marketplace (Claude / Cursor)

- The **plugin source repo must be public** (GitHub **Settings → General → Danger Zone → Change repository visibility**) for marketplace installs that pull from GitHub.
- After listing or updating the plugin, run a **post-publish smoke test** on a clean machine or container:
  - Claude Code: `/plugin marketplace add https://github.com/<org>/<repo>` then install the plugin per published instructions; `/reload-plugins` and invoke one **`/llm-wiki:`** command.
  - Confirm **`bin/llm-wiki --version`** works from a clone at the tagged revision.

Document marketplace-specific steps in **`README.md`** and **[`docs/INSTALL.md`](./INSTALL.md)** as needed; keep this file for maintainer checks.

## Pre-release (tracked files)

Do not tag a release with **uncommitted** changes that CI expects (plugin contracts, registry tests). Run **`bin/llm-wiki sync-agent-docs --check`** and **`bin/llm-wiki smoke-test`** before tagging. See [`CONTRIBUTING.md`](../CONTRIBUTING.md).
