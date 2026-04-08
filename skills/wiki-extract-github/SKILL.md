---
name: wiki-extract-github
description: Extract GitHub repo README, issues, PRs, releases, and changelogs into raw/. Use when a GitHub URL is shared or tracking a project.
disable-model-invocation: true
argument-hint: "<GitHub repo URL or owner/repo>"
---

# Wiki extract — GitHub

Extracts structured content from GitHub repositories into `raw/` for wiki ingestion. Use when:
- The user shares a GitHub repo URL to research or summarize.
- A library, tool, or project needs to be tracked in the vault.
- "Summarize this repo", "add this project to the wiki", "get the changelog for X".
- Following a project's release history or issue discussions.

---

## Step 1 — Identify the URL type

| Input | Content to extract |
|-------|-------------------|
| `github.com/<owner>/<repo>` (root) | README + metadata + recent releases |
| `github.com/<owner>/<repo>/releases` | All release notes |
| `github.com/<owner>/<repo>/issues/<N>` | Single issue thread |
| `github.com/<owner>/<repo>/pull/<N>` | Single PR + review comments |
| `github.com/<owner>/<repo>/blob/<branch>/CHANGELOG.md` | Raw changelog file |
| GitHub search query or org name | Ask user which repos to include |

---

## Step 2 — Check credentials

```bash
# Check if gh CLI is available (preferred)
gh --version

# Check if GITHUB_TOKEN is set (for REST API)
echo "${GITHUB_TOKEN:0:8}..."

# If neither is available, fall back to unauthenticated REST (60 req/hr limit)
# Inform user: "Using unauthenticated GitHub API — rate limit is 60 requests/hour.
# Run 'gh auth login' or export GITHUB_TOKEN for higher limits."
```

---

## Step 3 — Extract repo metadata and README

### Using gh CLI (preferred)

```bash
OWNER="<owner>"
REPO="<repo>"
SLUG="${OWNER}-${REPO}"
OUT_DIR="raw/projects/${SLUG}"
mkdir -p "$OUT_DIR"

# Repo metadata
gh repo view "${OWNER}/${REPO}" --json \
  name,description,stargazerCount,forkCount,primaryLanguage,topics,licenseInfo,\
  createdAt,updatedAt,url,homepageUrl,isArchived,defaultBranchRef \
  > "${OUT_DIR}/meta.json"

# README (raw markdown)
gh api "repos/${OWNER}/${REPO}/readme" \
  --jq '.content' | base64 -d > "${OUT_DIR}/README.md"
```

### Using REST API (fallback)

```bash
OWNER="<owner>"
REPO="<repo>"

# Metadata
curl -s -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  "https://api.github.com/repos/${OWNER}/${REPO}" \
  > /tmp/gh-meta.json

# README
curl -s -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github.raw" \
  "https://api.github.com/repos/${OWNER}/${REPO}/readme" \
  > /tmp/README.md
```

---

## Step 4 — Extract release notes

```bash
# Get last 10 releases via gh CLI
gh api "repos/${OWNER}/${REPO}/releases?per_page=10" \
  --jq '.[] | {tag: .tag_name, name: .name, date: .published_at, body: .body}' \
  > "${OUT_DIR}/releases.json"

# Format as markdown
python3 << 'PYEOF'
import json, pathlib, sys

releases = json.loads(pathlib.Path(sys.argv[1]).read_text())
out = []
for r in releases:
    out.append(f"## {r['tag']} — {r['name']} ({r['date'][:10]})\n\n{r['body']}\n")
print('\n---\n'.join(out))
PYEOF
python3 -c "..." "${OUT_DIR}/releases.json" > "${OUT_DIR}/release-notes.md"
```

---

## Step 5 — Extract CHANGELOG (if present)

```bash
# Try common CHANGELOG file names
for fname in CHANGELOG.md CHANGELOG.rst HISTORY.md CHANGES.md; do
    gh api "repos/${OWNER}/${REPO}/contents/${fname}" \
      --jq '.content' 2>/dev/null | base64 -d > "${OUT_DIR}/CHANGELOG.md" && break
done

# Fallback: check if repo has a releases page and use that instead
# (already covered in Step 4)
```

---

## Step 6 — Extract issues (optional, on request)

Only extract issues if the user specifically asks ("summarize recent issues", "what bugs are open?").

```bash
# Open issues, last 20, sorted by updated
gh issue list --repo "${OWNER}/${REPO}" \
  --state open --limit 20 \
  --json number,title,body,createdAt,updatedAt,labels,url \
  > "${OUT_DIR}/issues-open.json"

# Closed issues (bug reports, feature discussions)
gh issue list --repo "${OWNER}/${REPO}" \
  --state closed --limit 20 \
  --json number,title,body,createdAt,closedAt,labels,url \
  > "${OUT_DIR}/issues-closed.json"
```

For a single issue thread (including comments):

```bash
ISSUE_NUM=<N>
gh issue view "$ISSUE_NUM" --repo "${OWNER}/${REPO}" \
  --json number,title,body,comments,createdAt,closedAt,labels,url \
  > "${OUT_DIR}/issue-${ISSUE_NUM}.json"
```

---

## Step 7 — Write to raw/ with frontmatter

Output path: `raw/projects/<owner>-<repo>/index.md`

```bash
cat > "${OUT_DIR}/index.md" << EOF
---
title: "<Repo Name>"
owner: "<owner>"
repo: "<repo>"
source_url: https://github.com/${OWNER}/${REPO}
source_type: github_repo
language: "<primary language>"
stars: <N>
forks: <N>
topics: [<tag1>, <tag2>]
license: "<SPDX id>"
created_date: YYYY-MM-DD
last_updated: YYYY-MM-DD
is_archived: false
fetched_date: $(date +%Y-%m-%d)
---

# <Repo Name>

**Owner:** [${OWNER}](https://github.com/${OWNER})
**Stars:** <N> | **Language:** <lang> | **License:** <license>
**Topics:** <tag1>, <tag2>

## Description

<repo description>

## README

EOF
cat "${OUT_DIR}/README.md" >> "${OUT_DIR}/index.md"
```

---

## Step 8 — Handle large repos or monorepos

If the README is over 5,000 words:
1. Summarize the README to a 500-word digest and include both: `README-full.md` (raw) + `README-digest.md` (summary).
2. Note `readme_truncated: true` in frontmatter.

If the repo is a monorepo with multiple packages:
- Create one subfolder per package: `raw/projects/<slug>/<package>/`
- Extract only the top-level README and each package's README.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `gh: command not found` | `brew install gh` then `gh auth login` |
| `API rate limit exceeded` | Export `GITHUB_TOKEN` or run `gh auth login` |
| `404 Not Found` | Repo is private; need a token with `repo` scope |
| README is empty | Repo may use `readme.md` (lowercase); try `contents/readme.md` |
| No releases found | Check `tags` endpoint as fallback: `gh api repos/${OWNER}/${REPO}/tags` |
| CHANGELOG not found | Check `docs/CHANGELOG.md` or releases page |
| `base64: invalid input` | GitHub API returns base64 with line breaks; pipe through `base64 -d` or use `--jq` decode |

---

## Done looks like

- **`raw/projects/<owner>-<repo>/`** contains **`index.md`** (or agreed layout) with README + metadata; optional issues/releases JSON when requested.
- Rate limits and auth gaps were communicated to the user.

## Related skills

- **wiki-research-web** — for general web pages; GitHub README can also be fetched via Firecrawl but loses structure
- **wiki-research-academic** — for papers referenced in a repo's README
- **wiki-research-social** — for HN "Show HN" discussions or Twitter threads about a repo
- **wiki-extract-paywall** — not needed for public repos; private repos require `GITHUB_TOKEN`
- **wiki-raw-prepare** — clean and restructure the extracted markdown before wiki ingestion

## Smoke check

- **CLI:** Run `llm-wiki integrations status` and any `llm-wiki` line from Step 1 of this skill (from the vault root).
- **Prompt:** Invoke this skill by name in Claude Code; complete Step 1 only and confirm expected CLI or file output.

