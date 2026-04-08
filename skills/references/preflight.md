# Pre-flight Check — Shared Pattern for All Skills

Include this check at the top of any skill that requires a configured vault. It takes < 5 seconds and prevents confusing failures mid-session.

---

## The Pattern (copy into any skill)

Add a **Pre-flight** section before Step 1:

```markdown
## Pre-flight check

Before starting, verify the vault is set up and ready:

```bash
python3 << 'PYEOF'
import json, pathlib, os, sys

# ── 1. Config exists? ──────────────────────────────────────────
cfg_path = pathlib.Path('llm-wiki/config.json')
if not cfg_path.exists():
    print("PRE_FLIGHT: FAIL — llm-wiki/config.json not found")
    print("ACTION: Run wiki-setup to initialize the vault.")
    sys.exit(1)

cfg = json.loads(cfg_path.read_text())

# ── 2. Setup wizard completed? ─────────────────────────────────
meta = cfg.get('_meta', {})
if not meta.get('setup_completed'):
    print("PRE_FLIGHT: WARN — Setup not completed")
    print("ACTION: Run wiki-setup to finish configuration.")
    # Non-fatal: continue anyway, but warn the user

# ── 3. Required adapters enabled? ──────────────────────────────
# (Customize this list per skill)
required = []   # e.g. ['firecrawl'] or ['perplexity']
missing = []
for adapter in required:
    entry = cfg.get('integrations', {}).get(adapter, {})
    if not entry.get('enabled', True):
        missing.append(adapter)
    key_var = entry.get('api_key_env', '')
    if key_var and not os.environ.get(key_var):
        missing.append(f"{adapter} ({key_var} not set)")

if missing:
    print(f"PRE_FLIGHT: WARN — Missing: {', '.join(missing)}")
    print("ACTION: Run llm-wiki integrations wizard to configure them.")
else:
    print("PRE_FLIGHT: OK")
PYEOF
```

**On `PRE_FLIGHT: FAIL`** — stop and offer to run **wiki-setup**.
**On `PRE_FLIGHT: WARN`** — tell the user, then ask:
  - `[1]` Continue anyway (some features may not work)
  - `[2]` Run wiki-setup / integrations wizard first
  - `[3]` Cancel
**On `PRE_FLIGHT: OK`** — proceed normally.
```

---

## Lightweight Version (for quick skills)

For skills that just need to check the setup flag without adapter checks:

```bash
python3 -c "
import json, pathlib, sys
p = pathlib.Path('llm-wiki/config.json')
if not p.exists() or not json.loads(p.read_text()).get('_meta',{}).get('setup_completed'):
    print('⚠  wiki-llm setup not completed — run wiki-setup')
    sys.exit(1)
print('✓  vault ready')
" && echo "PREFLIGHT_PASS" || echo "PREFLIGHT_FAIL"
```

If `PREFLIGHT_FAIL`: offer to invoke **wiki-setup** for the user.

---

## State Flags Reference

These flags live in `llm-wiki/config.json` under `_meta`:

| Flag | Type | Meaning |
|------|------|---------|
| `_meta.setup_completed` | bool | Full wizard was run and confirmed |
| `_meta.setup_date` | string (ISO) | Date wizard was last completed |
| `_meta.setup_version` | string | Config schema version at setup time |

Read them with:
```python
cfg = json.loads(pathlib.Path('llm-wiki/config.json').read_text())
meta = cfg.get('_meta', {})
setup_ok = meta.get('setup_completed', False)
```

---

## Integration-specific Checks

Each skill knows which integrations it needs. Use this table to build the `required` list:

| Skill | Required integrations |
|-------|-----------------------|
| wiki-research-web | `firecrawl` (or `brave`) |
| wiki-research-news | `perplexity` (or `brave`) |
| wiki-research-social | `twitter` (for threads/search; zero-config for public tweets) |
| wiki-research-academic | none (arXiv is public) |
| wiki-research-feeds | none (feed CLI or stdlib) |
| wiki-extract-youtube | none (`yt-dlp` is a CLI tool, not an API key integration) |
| wiki-extract-paywall | none (bypass services are free/public) |
| wiki-extract-annas | `annas_archive` (for fast download; search is free) |
| wiki-extract-ebook | none (Python packages, not API keys) |

---

## How to Add Pre-flight to a Skill

1. Copy the **Pattern** block above into your skill's SKILL.md.
2. Fill in the `required = []` list with adapters your skill actually needs.
3. Place it before Step 1 (but after the frontmatter and intro).
4. The warn/fail messaging should always offer to run `wiki-setup` or `llm-wiki integrations wizard`.

---

## EVal Checkpoints (for long-running skills)

For multi-step skills (e.g. wiki-research-deep), add intermediate EVAL checkpoints:

```markdown
### EVAL checkpoint after <step name>

Before proceeding to the next step, verify:
- [ ] Expected files exist in raw/ (check with `ls raw/<expected-path>/`)
- [ ] No prompt-injection flags in new files (`llm-wiki raw validate`)
- [ ] File size is reasonable (> 200 words, < 50,000 words)
- [ ] No errors in the previous step's output

If any check fails: stop, report what failed, and ask the user whether to retry, skip, or abort.
```

This pattern prevents silent failures from cascading through multi-step workflows.
