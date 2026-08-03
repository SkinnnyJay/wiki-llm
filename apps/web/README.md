# `apps/web` — Agent desk (Vercel AI SDK + acpx + Claude Code)

Two-column UI: left **workspace explorer** (sessions / threads), right **chat** powered by the [Vercel AI SDK](https://sdk.vercel.ai/) (`useChat` + `DefaultChatTransport`) and **[AI Elements](https://elements.ai-sdk.dev/)** — composable chat primitives (`Conversation`, `Message` + `MessageResponse` with streaming markdown via Streamdown, `PromptInput`, `Suggestions`, etc.) installed under `src/components/ai-elements/` via `npx shadcn@latest add @ai-elements/...`.

The API route streams assistant output by running [`acpx`](https://github.com/openclaw/acpx) with `claude` (Claude Code over ACP) and `--format json`.

**System prompt:** Claude does not get a separate argv from acpx; the server **prepends** the markdown file `prompts/wiki-llm-chat-system.md` (wiki-llm context + Agent desk role) to each user turn in the temp file passed to `--file`. Override with `ACP_SYSTEM_PROMPT_PATH`, or disable with `ACP_SKIP_SYSTEM_PROMPT=1`.

Add more AI Elements components any time:

```bash
cd apps/web
npx shadcn@latest add @ai-elements/reasoning --yes
```

## Prereqs

- Node 20+
- Claude Code installed and available to acpx (`acpx claude …` as in the acpx README)
- `npx acpx@latest` working on the machine that runs Next.js

## Setup (localhost only)

This app is for a **trusted operator on loopback**. Do not expose it on a public interface without a separate threat review.

```bash
cd apps/web
cp .env.example .env.local
# Set ACP_WORKSPACE, ACP_WEB_TOKEN, and NEXT_PUBLIC_ACP_WEB_TOKEN (same secret).
# Optionally set LLM_WIKI_PLUGIN_ROOT if the server cannot walk up to the plugin checkout.
npm install
npm run typecheck   # optional
npm run dev         # binds 127.0.0.1:3000
```

Open `http://127.0.0.1:3000` (not a LAN/public bind by default).

For a production-style local check (no Claude/acpx invocation), run:

```bash
npm run build
npm run test:http
```

`test:http` starts the built server on a temporary loopback port and verifies the
token, host, and invalid-request boundaries. It does not send a valid chat turn
or require credentials for Claude.

`ACP_WEB_TOKEN` is **required**. `/api/chat` and `/api/config` reject missing or invalid tokens (SHA-256 + `crypto.timingSafeEqual`), and reject non-loopback `Host` / `X-Forwarded-Host`. The browser sends the matching `NEXT_PUBLIC_ACP_WEB_TOKEN` as `Authorization: Bearer …` / `X-ACP-Web-Token` (visible in the client bundle — localhost desk only).

## How it works

- **POST `/api/chat`** — Requires a valid web token and a well-formed message array plus a simple session identifier (`A-Z`, `a-z`, digits, `.`, `_`, `-`; 64 characters maximum) before resolving the wiki-llm plugin (`skills/wiki-setup/SKILL.md`) and vault state. If skills cannot be found, returns **503** until you set `LLM_WIKI_PLUGIN_ROOT` or `ACP_WORKSPACE` correctly; override with `ACP_WEB_SKIP_SKILL_CHECK=1` (not recommended). Then ensures `acpx claude sessions ensure --name …` and streams `npx acpx@latest --format json --cwd $ACP_WORKSPACE claude -s <session> --file <prompt>`. Each turn’s system payload includes **installed skill names** and paths so the model follows the same workflows as **`skills/*/SKILL.md`**.
- **GET `/api/config`** — Same token gate. Workspace display name, vault path, vault setup state, and plugin **preflight** (skill count, paths) for the sidebar.

Session names map to acpx `-s` parallel sessions; the UI keeps a lightweight “recent threads” list in memory (resets on refresh).

## Notes

- acpx is **alpha**; CLI output shapes may change — the NDJSON parser in `src/lib/acpx.ts` may need tweaks as upstream evolves.
- This app is **not** edge-compatible: the chat route uses Node `child_process` and `runtime = "nodejs"`.

## Phase 2 status and trust boundary

This is an optional graduate-path app, not part of the default plugin install or release runtime. Its source is tracked; `node_modules/`, `.next/`, local env files, and generated TypeScript state remain ignored.

The server route starts `acpx`/Claude with the configured `ACP_WORKSPACE`, which gives authenticated requests the effective authority of that local workspace. Run it only for trusted users on **localhost**, keep `ACP_WEB_TOKEN` in server-side env (and the matching `NEXT_PUBLIC_` value for the desk UI), and do not expose it publicly — this is not multi-tenant SaaS auth.
