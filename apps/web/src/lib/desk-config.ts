import type { DeskConfig, PreflightClient } from "@/types/desk";
import {
  ACPX_PERMISSION_MODES,
  DEFAULT_ACPX_PERMISSION_MODE,
  DEFAULT_VAULT_SETUP,
  VAULT_SETUP_STATES,
} from "@/types/desk";

export const DEFAULT_PREFLIGHT: PreflightClient = {
  pluginRoot: null,
  skillsResolvedFrom: null,
  skillCount: 0,
  skillNames: [],
  skillsReady: false,
  vaultSetup: DEFAULT_VAULT_SETUP,
  llmWikiBinExists: false,
  readyForClaude: false,
  chatAllowed: false,
  skillGateSkipped: false,
  issues: [],
};

export const DEFAULT_DESK_CONFIG: DeskConfig = {
  workspacePath: "",
  displayName: "Loading…",
  vaultPath: "",
  vaultExists: false,
  vaultSetup: DEFAULT_VAULT_SETUP,
  acpxPermissionMode: DEFAULT_ACPX_PERMISSION_MODE,
  preflight: DEFAULT_PREFLIGHT,
};

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function optionalString(record: Record<string, unknown>, key: string, fallback: string): string | null {
  const value = record[key];
  return value === undefined ? fallback : typeof value === "string" ? value : null;
}

function optionalBoolean(record: Record<string, unknown>, key: string, fallback: boolean): boolean | null {
  const value = record[key];
  return value === undefined ? fallback : typeof value === "boolean" ? value : null;
}

function optionalStringArray(record: Record<string, unknown>, key: string, fallback: string[]): string[] | null {
  const value = record[key];
  if (value === undefined) return fallback;
  return Array.isArray(value) && value.every((item) => typeof item === "string") ? value : null;
}

function optionalUnion<T extends readonly string[]>(
  record: Record<string, unknown>,
  key: string,
  allowed: T,
  fallback: T[number],
): T[number] | null {
  const value = record[key];
  if (value === undefined) return fallback;
  return typeof value === "string" && allowed.includes(value) ? value : null;
}

function decodePreflight(value: unknown): PreflightClient | null {
  if (value === undefined) return DEFAULT_PREFLIGHT;
  const record = asRecord(value);
  if (!record) return null;

  const pluginRoot = record.pluginRoot;
  const skillsResolvedFrom = record.skillsResolvedFrom;
  const skillCount = record.skillCount;
  const vaultSetup = optionalUnion(
    record,
    "vaultSetup",
    VAULT_SETUP_STATES,
    DEFAULT_VAULT_SETUP,
  );
  const skillNames = optionalStringArray(record, "skillNames", []);
  const issues = optionalStringArray(record, "issues", []);
  const skillsReady = optionalBoolean(record, "skillsReady", false);
  const llmWikiBinExists = optionalBoolean(record, "llmWikiBinExists", false);
  const readyForClaude = optionalBoolean(record, "readyForClaude", false);
  const chatAllowed = optionalBoolean(record, "chatAllowed", false);
  const skillGateSkipped = optionalBoolean(record, "skillGateSkipped", false);

  if (
    (pluginRoot !== undefined && pluginRoot !== null && typeof pluginRoot !== "string") ||
    (skillsResolvedFrom !== undefined && skillsResolvedFrom !== null && skillsResolvedFrom !== "env" && skillsResolvedFrom !== "walk") ||
    (skillCount !== undefined && (typeof skillCount !== "number" || !Number.isFinite(skillCount))) ||
    !vaultSetup ||
    !skillNames ||
    !issues ||
    skillsReady === null ||
    llmWikiBinExists === null ||
    readyForClaude === null ||
    chatAllowed === null ||
    skillGateSkipped === null
  ) {
    return null;
  }

  return {
    pluginRoot: pluginRoot ?? null,
    skillsResolvedFrom: skillsResolvedFrom ?? null,
    skillCount: skillCount ?? 0,
    skillNames,
    skillsReady,
    vaultSetup,
    llmWikiBinExists,
    readyForClaude,
    chatAllowed,
    skillGateSkipped,
    issues,
  };
}

/** Decode the localhost `/api/config` response before it reaches UI state. */
export function decodeDeskConfig(value: unknown): DeskConfig | null {
  const record = asRecord(value);
  if (!record || typeof record.workspacePath !== "string") return null;

  const displayName = optionalString(record, "displayName", "(unknown)");
  const vaultPath = optionalString(record, "vaultPath", "");
  const vaultExists = optionalBoolean(record, "vaultExists", false);
  const vaultSetup = optionalUnion(
    record,
    "vaultSetup",
    VAULT_SETUP_STATES,
    DEFAULT_VAULT_SETUP,
  );
  const acpxPermissionMode = optionalUnion(
    record,
    "acpxPermissionMode",
    ACPX_PERMISSION_MODES,
    DEFAULT_ACPX_PERMISSION_MODE,
  );
  const preflight = decodePreflight(record.preflight);

  if (
    displayName === null ||
    vaultPath === null ||
    vaultExists === null ||
    !vaultSetup ||
    !acpxPermissionMode ||
    !preflight
  ) {
    return null;
  }

  return {
    workspacePath: record.workspacePath,
    displayName,
    vaultPath,
    vaultExists,
    vaultSetup,
    acpxPermissionMode,
    preflight,
  };
}
