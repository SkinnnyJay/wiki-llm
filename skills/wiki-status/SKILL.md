---
name: wiki-status
description: Vault health dashboard — setup state, integrations, CLI, packages, MCP, git, config. Use for "status", "health check", or pre-research.
allowed-tools: Read Grep Glob Bash
---

# Wiki status — health dashboard

Produces a formatted health report for the current vault. Run this at the start of any session to verify that all required tools, keys, and config are in place before doing research or ingest work.

---

## Step 1 — Load config and vault state

```bash
# Verify vault root exists
ls llm-wiki/config.json 2>/dev/null && echo "CONFIG_FOUND" || echo "CONFIG_MISSING"

# Read setup completion flag
python3 << 'PYEOF'
import json, pathlib, sys

cfg_path = pathlib.Path('llm-wiki/config.json')
if not cfg_path.exists():
    print("SETUP_STATE: ✗ NOT STARTED — run wiki-setup to initialize")
    sys.exit(0)

cfg = json.loads(cfg_path.read_text())
meta = cfg.get('_meta', {})
if meta.get('setup_completed'):
    date = meta.get('setup_date', 'unknown date')
    ver  = meta.get('setup_version', '?')
    print(f"SETUP_STATE: ✓ COMPLETED ({date}, config v{ver})")
else:
    print("SETUP_STATE: ⚠ INCOMPLETE — run wiki-setup to finish configuration")
PYEOF
```

---

## Step 2 — Run integrations status

```bash
llm-wiki integrations status
```

Parse the output: each line has the adapter name and `checks=ok` or `checks=Set ...` (missing requirement).

---

## Step 3 — Check CLI tools

```bash
python3 << 'PYEOF'
import shutil, subprocess, sys

tools = [
    ("llm-wiki",     "llm-wiki --version",       "Core CLI — required"),
    ("firecrawl",    "firecrawl --version",       "JS-rendered web fetching"),
    ("yt-dlp",       "yt-dlp --version",          "YouTube transcript/download"),
    ("pytube",       "python3 -c 'import pytube; print(pytube.__version__)'", "YouTube (fallback)"),
    ("marker",       "marker --help",             "AI PDF extraction"),
    ("ebook-convert","ebook-convert --version",   "MOBI/AZW3 extraction (Calibre)"),
    ("ddjvu",        "ddjvu --help",              "DJVU text extraction"),
    ("whisper",      "whisper --help",            "Audio transcription"),
    ("git",          "git --version",             "Vault git snapshots"),
    ("feed",         "feed --version",            "RSS/Atom feed CLI"),
]

rows = []
for name, cmd, desc in tools:
    try:
        result = subprocess.run(cmd.split(), capture_output=True, timeout=5)
        status = "✓" if result.returncode == 0 else "⚠"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        status = "✗"
    rows.append((status, name, desc))

print("\n=== CLI TOOLS ===")
for status, name, desc in rows:
    print(f"  {status}  {name:<20} {desc}")
PYEOF
```

---

## Step 4 — Check Python packages

```bash
python3 << 'PYEOF'
packages = [
    ("ebooklib",      "EPUB extraction"),
    ("bs4",           "HTML parsing (BeautifulSoup)"),
    ("fitz",          "PDF extraction (PyMuPDF)"),
    ("pytube",        "YouTube (pytube)"),
    ("yt_dlp",        "YouTube (yt-dlp)"),
    ("yaml",          "YAML research-tasks support"),
    ("requests",      "HTTP requests"),
    ("anthropic",     "Claude Vision PDF adapter"),
    ("openai",        "OpenAI adapter (optional)"),
    ("marker",        "Marker PDF adapter"),
]

print("\n=== PYTHON PACKAGES ===")
for pkg, desc in packages:
    try:
        mod = __import__(pkg)
        ver = getattr(mod, '__version__', '?')
        print(f"  ✓  {pkg:<20} {desc}  ({ver})")
    except ImportError:
        print(f"  ✗  {pkg:<20} {desc}  (not installed)")
PYEOF
```

---

## Step 5 — Check environment variables / API keys

```bash
python3 << 'PYEOF'
import os

keys = [
    ("FIRECRAWL_API_KEY",     "Firecrawl web fetching"),
    ("PERPLEXITY_API_KEY",    "Perplexity AI research"),
    ("BRAVE_SEARCH_API_KEY",  "Brave Search"),
    ("TWITTER_AUTH_TOKEN",    "Twitter/X full threads"),
    ("ANTHROPIC_API_KEY",     "Claude Vision PDF + AI features"),
    ("OPENAI_API_KEY",        "OpenAI adapter (optional)"),
    ("NEWS_API_KEY",          "NewsAPI (optional)"),
    ("ANNAS_ARCHIVE_KEY",     "Anna's Archive ebook download"),
]

print("\n=== API KEYS / ENV VARS ===")
for var, desc in keys:
    val = os.environ.get(var, '')
    if val:
        masked = val[:4] + '...' + val[-2:] if len(val) > 8 else '***'
        print(f"  ✓  {var:<28} {desc}  ({masked})")
    else:
        print(f"  ✗  {var:<28} {desc}  (not set)")
PYEOF
```

---

## Step 6 — Check vault structure

```bash
python3 << 'PYEOF'
import pathlib

vault = pathlib.Path('llm-wiki')
dirs = [
    ("llm-wiki/",            "Vault root"),
    ("llm-wiki/wiki/",       "Curated wiki pages"),
    ("llm-wiki/raw/",        "Ingested sources"),
    ("llm-wiki/wiki/index.md", "Wiki index"),
    ("llm-wiki/wiki/log.md",  "Wiki change log"),
    ("llm-wiki/config.json",  "Vault config"),
    ("llm-wiki/CLAUDE.md",    "Vault agent rules"),
]

print("\n=== VAULT STRUCTURE ===")
for path, desc in dirs:
    p = pathlib.Path(path)
    exists = p.exists()
    print(f"  {'✓' if exists else '✗'}  {path:<35} {desc}")

# Count raw/ and wiki/ files
raw_count  = len(list(pathlib.Path('llm-wiki/raw').rglob('*.md')))  if pathlib.Path('llm-wiki/raw').exists()  else 0
wiki_count = len(list(pathlib.Path('llm-wiki/wiki').rglob('*.md'))) if pathlib.Path('llm-wiki/wiki').exists() else 0
print(f"\n  raw/  files: {raw_count}")
print(f"  wiki/ files: {wiki_count}")
PYEOF
```

---

## Step 7 — Check config settings

```bash
python3 << 'PYEOF'
import json, pathlib

cfg_path = pathlib.Path('llm-wiki/config.json')
if not cfg_path.exists():
    print("\n=== CONFIG ===\n  ✗  config.json not found — run wiki-setup")
    exit()

cfg = json.loads(cfg_path.read_text())

print("\n=== CONFIG SETTINGS ===")
print(f"  persona.name          : {cfg.get('persona',{}).get('name','Gennie')}")
print(f"  git.enabled           : {cfg.get('git',{}).get('enabled', False)}")
print(f"  research_loop.enabled : {cfg.get('research_loop',{}).get('enabled', False)}")
print(f"  ingestion_security    : {cfg.get('ingestion_security',{}).get('enabled', True)}")
print(f"  pdf.default_adapter   : {cfg.get('pdf',{}).get('default_adapter','pdf')}")
print(f"  viewer.og_base_url    : {cfg.get('viewer',{}).get('og_base_url','(not set)') or '(not set)'}")
print(f"  viewer.open_file_scheme: {cfg.get('viewer',{}).get('open_file_scheme','file')}")

print("\n=== INTEGRATIONS (from config) ===")
for k, v in cfg.get('integrations', {}).items():
    enabled = v.get('enabled', True)
    key_var = v.get('api_key_env', '—')
    print(f"  {'✓' if enabled else '○'}  {k:<20} enabled={str(enabled):<5}  key_env={key_var}")
PYEOF
```

---

## Step 8 — Check MCP servers

```bash
python3 << 'PYEOF'
import pathlib, json

# Check Cursor MCP config (macOS path)
mcp_paths = [
    pathlib.Path.home() / '.cursor' / 'mcp.json',
    pathlib.Path.home() / '.claude' / 'claude_desktop_config.json',
    pathlib.Path('mcp.json'),
]

relevant_mcps = {
    'context7': 'Documentation lookup',
    'playwright': 'Browser automation',
    'redis':    'Caching/state',
    'github':   'GitHub integration',
    'fetch':    'Raw HTTP fetching',
    'memory':   'Persistent agent memory',
    'prisma':   'Database access',
}

found_any = False
for mcp_path in mcp_paths:
    if not mcp_path.exists():
        continue
    found_any = True
    try:
        data = json.loads(mcp_path.read_text())
        servers = data.get('mcpServers', {})
        print(f"\n=== MCP SERVERS ({mcp_path}) ===")
        for name, _ in servers.items():
            desc = relevant_mcps.get(name, 'installed')
            print(f"  ✓  {name:<25} {desc}")
        # Check for any relevant ones that are missing
        for name, desc in relevant_mcps.items():
            if name not in servers:
                print(f"  ○  {name:<25} {desc}  (not installed)")
    except Exception as e:
        print(f"  ⚠  Could not parse {mcp_path}: {e}")

if not found_any:
    print("\n=== MCP SERVERS ===\n  ○  No MCP config found (optional)")
PYEOF
```

---

## Step 9 — Print summary

After all checks, print a compact summary:

```bash
python3 << 'PYEOF'
print("""
╔══════════════════════════════════════════════════════╗
║                  wiki-llm STATUS                     ║
╠══════════════════════════════════════════════════════╣
║  ✓  = installed / configured / enabled               ║
║  ⚠  = installed but not configured or degraded       ║
║  ✗  = missing / not set                              ║
║  ○  = optional / not installed                       ║
╚══════════════════════════════════════════════════════╝
""")
PYEOF
# (Results from steps 1–8 appear above this box)
```

**If setup is incomplete:** Offer to run **wiki-setup** immediately.
**If integrations have ✗ keys:** Offer to run `llm-wiki integrations wizard` for each missing one.
**If vault structure is missing dirs:** Offer to run `llm-wiki setup --root .`.

---

## Done looks like

- All steps 1–9 completed (or skipped with reason); summary box printed.
- User sees setup state, integrations, CLI/Python tooling, API keys (masked), vault paths, config flags, and optional MCP inventory.
- If setup is incomplete or tools are missing, user is pointed to **wiki-setup** or **`llm-wiki integrations wizard`**.

## Quick invocation

This skill can be invoked as a one-liner pre-flight by other skills using the pattern in `skills/references/preflight.md`.

---

## Related skills

- **wiki-setup** — full setup wizard; invoke when status shows setup incomplete
- `skills/references/preflight.md` — lightweight pre-flight check pattern used by research/ingest skills

## Smoke check

- **CLI:** Run `llm-wiki integrations status` and any `llm-wiki` line from Step 1 of this skill (from the vault root).
- **Prompt:** Invoke this skill by name in Claude Code; complete Step 1 only and confirm expected CLI or file output.

