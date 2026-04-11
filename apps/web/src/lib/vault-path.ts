import { existsSync } from "node:fs";
import { join } from "node:path";

/**
 * Resolve the llm-wiki vault directory for prompts and UI.
 * - `LLM_WIKI_VAULT`: absolute path, or path relative to the git workspace (`ACP_WORKSPACE`).
 * - default: `<workspace>/llm-wiki` (whether or not it exists yet).
 */
export function resolveVaultPath(workspaceRoot: string): string {
  const fromEnv = process.env.LLM_WIKI_VAULT?.trim();
  if (!fromEnv) {
    return join(workspaceRoot, "llm-wiki");
  }
  if (fromEnv.startsWith("/") || /^[A-Za-z]:\\/.test(fromEnv)) {
    return fromEnv;
  }
  return join(workspaceRoot, fromEnv);
}

export function vaultExistsAt(path: string): boolean {
  try {
    return existsSync(path);
  } catch {
    return false;
  }
}
