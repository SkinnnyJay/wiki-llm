export const VAULT_SETUP_STATES = [
  "missing",
  "no_config",
  "incomplete",
  "ready",
] as const;

export type VaultSetupState = (typeof VAULT_SETUP_STATES)[number];
export const DEFAULT_VAULT_SETUP: VaultSetupState = "missing";

export const ACPX_PERMISSION_MODES = [
  "approve-reads",
  "approve-all",
  "deny-all",
] as const;

export type AcpxPermissionMode = (typeof ACPX_PERMISSION_MODES)[number];
export const DEFAULT_ACPX_PERMISSION_MODE: AcpxPermissionMode = "approve-reads";

export type PreflightClient = {
  pluginRoot: string | null;
  skillsResolvedFrom: "env" | "walk" | null;
  skillCount: number;
  skillNames: string[];
  skillsReady: boolean;
  vaultSetup: VaultSetupState;
  llmWikiBinExists: boolean;
  readyForClaude: boolean;
  chatAllowed: boolean;
  skillGateSkipped: boolean;
  issues: string[];
};

export type DeskConfig = {
  workspacePath: string;
  displayName: string;
  vaultPath: string;
  vaultExists: boolean;
  vaultSetup: VaultSetupState;
  acpxPermissionMode: AcpxPermissionMode;
  preflight: PreflightClient;
};
