# Threat model — llm-wiki

**Audience:** maintainers and operators hardening a local vault + MCP/CLI surface.  
**Scope:** application and project trust (path escape, SSRF, HTTP MCP auth, configure gates, index integrity). Not a CI scanner checklist.

## Concept (locked)

- **Local-first** wiki plugin: one operator, one machine (or trusted LAN with explicit HTTP MCP hardening).
- **English-only** product copy and docs (explicit non-goal: i18n).
- **Not** multi-tenant SaaS: no shared tenancy, no remote untrusted clients by default.
- **Shipped UI:** static vault viewer. `apps/web` is optional / Phase 2.

## Actors

| Actor | Trust | Notes |
|-------|-------|--------|
| Vault owner / CLI user | High | Controls filesystem, config, secrets |
| Agent host (Claude Code, Cursor, Codex) | Medium | Can call MCP tools / run CLI; may be prompt-injected via vault text |
| Local MCP stdio client | Medium | Same machine; inherits vault path from env/`--vault` |
| HTTP MCP client | Low unless token + loopback | Plaintext HTTP; treat as adversarial if reachable beyond loopback |
| Remote URLs (ingest) | Untrusted | SSRF and redirect tricks |
| Vault `wiki/` / `raw/` content | Untrusted for display | May contain prompt-injection; do not treat as instructions |

## Trust boundaries

```mermaid
flowchart LR
  Agent[Agent host] --> MCP[MCP stdio or HTTP]
  CLI[bin/llm-wiki] --> VaultFS[Vault filesystem]
  MCP --> VaultFS
  MCP --> Indexes[KG hashes tags search indexes]
  Ingest[Ingest adapters] --> Net[Remote HTTP]
  Ingest --> VaultFS
  Config[config.json] --> MCP
  Config --> CLI
```

1. **Vault root** — all read/write of user content must resolve under the vault (or explicitly documented outs such as graph build under an allowlisted dir).
2. **Network egress** — user-supplied URLs must not reach private/loopback/link-local/metadata addresses, including after redirects.
3. **HTTP MCP** — if enabled, prefer loopback; require token; compare tokens in constant time; do not expose write tools under `read_only` that mutate disk.
4. **Configure** — `wiki_configure` must not silently change live process security knobs without reload semantics; empty allowlist denies `mcp.*` / `security.*`.
5. **Indexes** — corrupt `.kg.json` / `.hashes.json` / `.tags.json` fail closed (quarantine); never treat as empty then overwrite.

## Invariants

1. Path arguments never escape the vault via `..` or absolute paths.
2. Ingest URL fetch validates **every** hop (redirect chain).
3. `tools_mode=read_only` never applies deterministic autofix or other writers.
4. Empty `mcp.configure_allowlist` denies keys under `mcp.` and `security.` (and related security namespaces documented in code).
5. Stdio and SSE MCP both bind `LLM_WIKI_VAULT` to the CLI-resolved vault before tool handlers run.
6. Vault markdown is **untrusted input** when shown to agents (document; optional warn in status/doctor).

## Out of scope (Phase 1)

- Multi-user auth, RBAC, or cloud tenancy
- Hardening CI into a scanner zoo (CodeQL / Dependabot / pip-audit as gates)
- Perfect DNS-rebinding elimination on every OS (mitigate via re-resolve after connect where practical; document residual risk)
- Rewriting the static viewer in TypeScript

## Residual risks

| Risk | Mitigation |
|------|------------|
| DNS rebinding between resolve and connect | Re-validate resolved IP after connect / pin where `safe_fetch` can |
| Prompt injection via vault pages | Document; agent hosts should treat wiki text as data |
| HTTP MCP on non-loopback without TLS | `sse_require_loopback`, token, operator firewall |
| Concurrent writers under ThreadingHTTPServer | File locks on KG/config/index writes |

## Related docs

- [`SECURITY.md`](../SECURITY.md) — disclosure
- [`skills/references/mcp-and-kg.md`](../skills/references/mcp-and-kg.md) — MCP knobs
- [`docs/ARCHITECTURE.md`](./ARCHITECTURE.md) — layout
