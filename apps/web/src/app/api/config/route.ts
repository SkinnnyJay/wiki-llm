import { acpxPermissionFlags, getWorkspaceDir } from "@/lib/acpx";
import { tryLoadSystemPrompt } from "@/lib/system-prompt";
import { resolveVaultPath, vaultExistsAt } from "@/lib/vault-path";
import { computeWikiPreflight, preflightForClient } from "@/lib/wiki-preflight";

export const runtime = "nodejs";

export async function GET() {
  const workspacePath = getWorkspaceDir();
  const displayName = workspacePath.split(/[/\\]/).filter(Boolean).pop() ?? workspacePath;
  const vaultPath = resolveVaultPath(workspacePath);
  const preflight = computeWikiPreflight(workspacePath);
  const system = tryLoadSystemPrompt();
  const permissionMode =
    process.env.ACP_ACPX_PERMISSION_MODE?.trim().toLowerCase() ?? "approve-reads";
  return Response.json({
    workspacePath,
    displayName,
    vaultPath,
    vaultExists: vaultExistsAt(vaultPath),
    vaultSetup: preflight.vaultSetup,
    preflight: preflightForClient(preflight),
    acpxPermissionMode: permissionMode,
    acpxPermissionFlags: acpxPermissionFlags(),
    acpxHint:
      "Requires `npx acpx@latest` and Claude Code (`acpx claude …`). Set ACP_WORKSPACE to the git repo you want the agent to use.",
    systemPrompt: system.ok
      ? {
          loaded: true,
          path: system.path,
          lengthChars: system.length,
        }
      : {
          loaded: false,
          path: system.path,
          error: system.error,
        },
  });
}
