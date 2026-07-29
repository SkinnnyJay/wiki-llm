import { readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import type { WikiPreflight } from "@/lib/wiki-preflight";
import { computeWikiPreflight } from "@/lib/wiki-preflight";
import { resolveVaultPath, vaultExistsAt } from "@/lib/vault-path";

/** Default: `apps/web/prompts/wiki-llm-chat-system.md` (anchored to this module, not `cwd`). */
const DEFAULT_PROMPT_FILE = join(
  dirname(fileURLToPath(import.meta.url)),
  "..",
  "..",
  "prompts",
  "wiki-llm-chat-system.md",
);

let cache: { path: string; content: string } | null = null;

/**
 * Resolve which file backs the Claude “system” context for acpx turns.
 * - `ACP_SYSTEM_PROMPT_PATH`: absolute path, or relative to `process.cwd()`
 * - default: `apps/web/prompts/wiki-llm-chat-system.md` next to the Next app
 */
export function resolveSystemPromptPath(): string {
  const fromEnv = process.env.ACP_SYSTEM_PROMPT_PATH?.trim();
  if (fromEnv) {
    if (fromEnv.startsWith("/") || /^[A-Za-z]:\\/.test(fromEnv)) {
      return fromEnv;
    }
    return join(process.cwd(), fromEnv);
  }
  return DEFAULT_PROMPT_FILE;
}

/**
 * Load the markdown system prompt for the chat client. Cached per path until
 * `invalidateSystemPromptCache()` is called (e.g. in tests).
 */
export function loadSystemPrompt(): string {
  const path = resolveSystemPromptPath();
  if (cache?.path === path) {
    return cache.content;
  }
  if (!existsSync(path)) {
    throw new Error(
      `System prompt file not found: ${path}. Create it or set ACP_SYSTEM_PROMPT_PATH.`,
    );
  }
  const content = readFileSync(path, "utf8");
  cache = { path, content };
  return content;
}

/** When `ACP_SKIP_SYSTEM_PROMPT=1`, no system block is prepended (user message only). */
export function getSystemPromptForTurn(): string {
  if (process.env.ACP_SKIP_SYSTEM_PROMPT?.trim() === "1") {
    return "";
  }
  return loadSystemPrompt();
}

export function tryLoadSystemPrompt():
  | { ok: true; path: string; length: number; skipped: boolean }
  | { ok: false; path: string; error: string; skipped: boolean } {
  if (process.env.ACP_SKIP_SYSTEM_PROMPT?.trim() === "1") {
    return {
      ok: true,
      path: resolveSystemPromptPath(),
      length: 0,
      skipped: true,
    };
  }
  try {
    const path = resolveSystemPromptPath();
    const content = loadSystemPrompt();
    return { ok: true, path, length: content.length, skipped: false };
  } catch (e) {
    const path = resolveSystemPromptPath();
    const msg = e instanceof Error ? e.message : String(e);
    return { ok: false, path, error: msg, skipped: false };
  }
}

export function invalidateSystemPromptCache(): void {
  cache = null;
}

/**
 * Injected each turn so the model sees concrete paths, installed skills, and policy.
 */
export function getRuntimeBoundariesMarkdown(
  workspaceRoot: string,
  preflight?: WikiPreflight,
): string {
  const pf = preflight ?? computeWikiPreflight(workspaceRoot);
  const vault = resolveVaultPath(workspaceRoot);
  const vaultOk = vaultExistsAt(vault);
  const skillLine =
    pf.skillsReady && pf.pluginRoot
      ? [
          `- **wiki-llm plugin root:** \`${pf.pluginRoot}\` (${pf.skillCount} skills under \`skills/\`)`,
          `- **Skill names (follow these workflows):** ${pf.skillNames.slice(0, 36).join(", ")}${pf.skillCount > 36 ? ", …" : ""}`,
        ]
      : [
          "- **wiki-llm plugin / skills:** not resolved on the server — ask the user to set `LLM_WIKI_PLUGIN_ROOT` or run the desk from inside the wiki-llm repo checkout.",
        ];

  const vaultSetupLine = (() => {
    switch (pf.vaultSetup) {
      case "ready":
        return `- **Vault setup:** complete (\`config.json\` + \`_meta.setup_completed\`)`;
      case "incomplete":
        return `- **Vault setup:** incomplete — prefer **wiki-setup** / \`llm-wiki setup\` before heavy pipeline work`;
      case "no_config":
        return `- **Vault setup:** no \`config.json\` — run **wiki-setup** first`;
      default:
        return `- **Vault setup:** vault directory missing — run **wiki-setup** or set \`LLM_WIKI_VAULT\``;
    }
  })();

  return [
    "## Runtime boundaries (enforced by this desk)",
    "",
    `- **Git workspace (acpx \`--cwd\`):** \`${workspaceRoot}\``,
    `- **llm-wiki vault path:** \`${vault}\`${vaultOk ? " (exists on disk)" : " (path not found yet — user may need \`llm-wiki setup\`)"}`,
    vaultSetupLine,
    "",
    ...skillLine,
    "",
    "You **must**:",
    "",
    "1. Treat **wiki-llm / vault work** as in-scope: \`llm-wiki/\`, \`raw/\`, \`wiki/\`, \`config.json\`, plugin \`bin/llm-wiki\`, \`skills/\`, \`commands/\`.",
    "2. **Refuse** tasks that are clearly unrelated (e.g. general web browsing, unrelated repos, destructive system commands) unless the user explicitly needs them *inside this workspace* for vault maintenance.",
    "3. **Follow the installed skills** (see list above): use **wiki-pipeline** for end-to-end flow, **wiki-status** before research, **wiki-research** / **wiki-fetch** for ingestion, **wiki-ingest** / **wiki-maintainer** for curation, **wiki-lint** before ship — do not improvise shortcuts that contradict \`WORKFLOWS.md\` and \`skills/references/\`.",
    "4. Prefer **slash commands** (\`commands/*.md\`) and **skills** over ad-hoc shell.",
    "5. **Do not** claim you ran tools you did not run; stay consistent with what acpx/Claude Code actually executes.",
    "",
    "The server may run acpx with **read-approval** defaults (\`--approve-reads\`) so writes need explicit approval — align your suggestions accordingly.",
  ].join("\n");
}

/** Full system block: file prompt + runtime boundaries (unless system prompt skipped). */
export function buildFullSystemPrompt(
  workspaceRoot: string,
  preflight?: WikiPreflight,
): string {
  const base = getSystemPromptForTurn();
  const pf = preflight ?? computeWikiPreflight(workspaceRoot);
  const runtime = getRuntimeBoundariesMarkdown(workspaceRoot, pf);
  if (!base.trim()) {
    return runtime;
  }
  return `${base.trim()}\n\n---\n\n${runtime}`;
}

/**
 * Body written to the temp file passed to `acpx --file`. acpx does not expose a
 * dedicated `--system` flag; injecting instructions here is the supported pattern.
 */
export function composeAcpxPromptFileBody(
  systemPrompt: string,
  userMessage: string,
): string {
  const sys = systemPrompt.trim();
  const user = userMessage.trim();
  if (!sys) return user;
  return [
    "<!-- acpx prompt payload: system instructions + user turn -->",
    "",
    "## System instructions (Agent desk)",
    "",
    sys,
    "",
    "---",
    "",
    "## User message",
    "",
    user,
    "",
  ].join("\n");
}
