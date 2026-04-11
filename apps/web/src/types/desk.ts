export type PreflightClient = {
  pluginRoot: string | null;
  skillsResolvedFrom: "env" | "walk" | null;
  skillCount: number;
  skillNames: string[];
  skillsReady: boolean;
  vaultSetup: string;
  llmWikiBinExists: boolean;
  readyForClaude: boolean;
  chatAllowed: boolean;
  skillGateSkipped: boolean;
  issues: string[];
};
