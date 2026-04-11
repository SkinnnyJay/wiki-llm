import { existsSync, readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";

import { resolveVaultPath, vaultExistsAt } from "@/lib/vault-path";

export type VaultSetupState = "missing" | "no_config" | "incomplete" | "ready";

export type WikiPreflight = {
  pluginRoot: string | null;
  skillsResolvedFrom: "env" | "walk" | null;
  skillNames: string[];
  skillCount: number;
  skillsReady: boolean;
  vaultPath: string;
  vaultSetup: VaultSetupState;
  llmWikiBinPath: string | null;
  llmWikiBinExists: boolean;
  /** False when the plugin skills tree cannot be found (blocks agent unless skip env). */
  readyForClaude: boolean;
  issues: string[];
};

function isWikiLlmPluginRoot(dir: string): boolean {
  return existsSync(join(dir, "skills", "wiki-setup", "SKILL.md"));
}

function walkAncestors(start: string, maxDepth: number): string[] {
  const out: string[] = [];
  let cur = start;
  for (let i = 0; i < maxDepth; i++) {
    out.push(cur);
    const parent = dirname(cur);
    if (parent === cur) break;
    cur = parent;
  }
  return out;
}

/**
 * Directory containing `skills/wiki-setup/SKILL.md` (wiki-llm plugin checkout).
 * - `LLM_WIKI_PLUGIN_ROOT` / `WIKI_LLM_ROOT` / `CLAUDE_PLUGIN_ROOT`: explicit path
 * - Else walk up from workspaceRoot (and process.cwd() if different)
 */
export function resolvePluginRepoRoot(workspaceRoot: string): {
  path: string | null;
  resolvedFrom: "env" | "walk" | null;
} {
  const envKeys = [
    "LLM_WIKI_PLUGIN_ROOT",
    "WIKI_LLM_ROOT",
    "CLAUDE_PLUGIN_ROOT",
  ] as const;
  for (const key of envKeys) {
    const raw = process.env[key]?.trim();
    if (!raw) continue;
    const expanded =
      raw.startsWith("/") || /^[A-Za-z]:\\/.test(raw)
        ? raw
        : join(process.cwd(), raw);
    if (isWikiLlmPluginRoot(expanded)) {
      return { path: expanded, resolvedFrom: "env" };
    }
  }

  const seeds = new Set<string>();
  seeds.add(workspaceRoot);
  seeds.add(process.cwd());

  for (const seed of seeds) {
    for (const dir of walkAncestors(seed, 12)) {
      if (isWikiLlmPluginRoot(dir)) {
        return { path: dir, resolvedFrom: "walk" };
      }
    }
  }

  return { path: null, resolvedFrom: null };
}

function readSkillName(skillDir: string, folderName: string): string {
  const skillFile = join(skillDir, folderName, "SKILL.md");
  if (!existsSync(skillFile)) return folderName;
  try {
    const head = readFileSync(skillFile, "utf8").split("\n").slice(0, 40).join("\n");
    const m = /^name:\s*(.+)$/m.exec(head);
    if (m) return m[1].trim();
  } catch {
    /* use folder */
  }
  return folderName;
}

export function listSkillNames(pluginRoot: string): string[] {
  const skillsDir = join(pluginRoot, "skills");
  if (!existsSync(skillsDir)) return [];
  const names: string[] = [];
  for (const ent of readdirSync(skillsDir, { withFileTypes: true })) {
    if (!ent.isDirectory()) continue;
    if (ent.name === "references") continue;
    const sub = join(skillsDir, ent.name, "SKILL.md");
    if (!existsSync(sub)) continue;
    names.push(readSkillName(skillsDir, ent.name));
  }
  return names.sort((a, b) => a.localeCompare(b));
}

export function readVaultSetupState(vaultPath: string): VaultSetupState {
  if (!vaultExistsAt(vaultPath)) return "missing";
  const cfgPath = join(vaultPath, "config.json");
  if (!existsSync(cfgPath)) return "no_config";
  try {
    const raw = readFileSync(cfgPath, "utf8");
    const cfg = JSON.parse(raw) as { _meta?: { setup_completed?: boolean } };
    if (cfg._meta?.setup_completed) return "ready";
    return "incomplete";
  } catch {
    return "no_config";
  }
}

export function computeWikiPreflight(workspaceRoot: string): WikiPreflight {
  const vaultPath = resolveVaultPath(workspaceRoot);
  const vaultSetup = readVaultSetupState(vaultPath);
  const { path: pluginRoot, resolvedFrom } = resolvePluginRepoRoot(workspaceRoot);

  const issues: string[] = [];
  let skillNames: string[] = [];
  let skillCount = 0;

  if (!pluginRoot) {
    issues.push(
      "wiki-llm plugin root not found (expected a directory containing skills/wiki-setup/SKILL.md). Set LLM_WIKI_PLUGIN_ROOT or point ACP_WORKSPACE inside the wiki-llm repo.",
    );
  } else {
    skillNames = listSkillNames(pluginRoot);
    skillCount = skillNames.length;
    if (skillCount === 0) {
      issues.push("skills/ exists but no SKILL.md entries were found.");
    }
  }

  const skillsReady = Boolean(pluginRoot && skillCount > 0);
  const llmWikiBinPath = pluginRoot ? join(pluginRoot, "bin", "llm-wiki") : null;
  const llmWikiBinExists = llmWikiBinPath ? existsSync(llmWikiBinPath) : false;
  if (pluginRoot && !llmWikiBinExists) {
    issues.push("bin/llm-wiki not found under plugin root (install or use PATH llm-wiki).");
  }

  if (vaultSetup === "missing") {
    issues.push("Vault directory missing — run llm-wiki setup or set LLM_WIKI_VAULT.");
  } else if (vaultSetup === "no_config") {
    issues.push("Vault has no config.json — initialize with wiki-setup / llm-wiki setup.");
  } else if (vaultSetup === "incomplete") {
    issues.push(
      "Vault setup not marked complete (_meta.setup_completed) — finish wiki-setup when ready.",
    );
  }

  const readyForClaude = skillsReady;

  return {
    pluginRoot,
    skillsResolvedFrom: resolvedFrom,
    skillNames,
    skillCount,
    skillsReady,
    vaultPath,
    vaultSetup,
    llmWikiBinPath,
    llmWikiBinExists,
    readyForClaude,
    issues,
  };
}

export function skipSkillPreflightGate(): boolean {
  return process.env.ACP_WEB_SKIP_SKILL_CHECK?.trim() === "1";
}

/** JSON-safe subset for `/api/config` and error responses. */
export function preflightForClient(pf: WikiPreflight) {
  const skipGate = skipSkillPreflightGate();
  return {
    pluginRoot: pf.pluginRoot,
    skillsResolvedFrom: pf.skillsResolvedFrom,
    skillCount: pf.skillCount,
    skillNames: pf.skillNames.slice(0, 48),
    skillsReady: pf.skillsReady,
    vaultSetup: pf.vaultSetup,
    llmWikiBinExists: pf.llmWikiBinExists,
    readyForClaude: pf.readyForClaude,
    /** True when POST /api/chat will run (skills found or ACP_WEB_SKIP_SKILL_CHECK=1). */
    chatAllowed: pf.readyForClaude || skipGate,
    skillGateSkipped: skipGate,
    issues: pf.issues,
  };
}
