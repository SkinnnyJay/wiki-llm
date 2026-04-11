<p align="center">
  <img src="assets/readme-banner.png" alt="llm-wiki" width="100%" />
</p>

<p align="center">
  <a href="https://github.com/SkinnnyJay/wiki-llm"><img src="https://img.shields.io/badge/GitHub-repo-181717?logo=github&logoColor=white" alt="GitHub repository"/></a>
  <a href="https://github.com/SkinnnyJay/wiki-llm#install-claude-code"><img src="https://img.shields.io/badge/Claude%20Code-plugin-D4A574?logo=anthropic&logoColor=white" alt="Claude Code: install instructions"/></a>
  <a href="https://github.com/SkinnnyJay/wiki-llm/blob/main/AGENTS.md"><img src="https://img.shields.io/badge/Cursor-rules%20%2B%20plugin-000000?logo=cursor&logoColor=white" alt="Cursor: AGENTS.md"/></a>
</p>


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
