"use client";

import * as React from "react";

import { AgentChatPanel } from "@/components/agent-chat-panel";
import { WorkspaceExplorer } from "@/components/workspace-explorer";
import { webAuthHeaders } from "@/lib/web-token-client";
import type { PreflightClient } from "@/types/desk";

function randomSessionName() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `thread-${crypto.randomUUID().slice(0, 8)}`;
  }
  return `thread-${Math.random().toString(16).slice(2, 10)}`;
}

export type DeskConfig = {
  workspacePath: string;
  displayName: string;
  vaultPath: string;
  vaultExists: boolean;
  vaultSetup: string;
  acpxPermissionMode: string;
  preflight: PreflightClient;
};

const defaultPreflight: PreflightClient = {
  pluginRoot: null,
  skillsResolvedFrom: null,
  skillCount: 0,
  skillNames: [],
  skillsReady: false,
  vaultSetup: "missing",
  llmWikiBinExists: false,
  readyForClaude: false,
  chatAllowed: false,
  skillGateSkipped: false,
  issues: [],
};

const defaultDesk: DeskConfig = {
  workspacePath: "",
  displayName: "Loading…",
  vaultPath: "",
  vaultExists: false,
  vaultSetup: "missing",
  acpxPermissionMode: "approve-reads",
  preflight: defaultPreflight,
};

export function ChatApp() {
  const [desk, setDesk] = React.useState<DeskConfig>(defaultDesk);
  const [sessionName, setSessionName] = React.useState("default");
  const [recentSessions, setRecentSessions] = React.useState<string[]>([
    "default",
  ]);

  React.useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await fetch("/api/config", {
          method: "GET",
          headers: webAuthHeaders(),
        });
        const data = (await res.json()) as Partial<DeskConfig> & {
          displayName?: string;
          preflight?: Partial<PreflightClient>;
          vaultSetup?: string;
        };
        if (cancelled) return;
        const pf = data.preflight;
        setDesk({
          workspacePath: data.workspacePath ?? "",
          displayName: data.displayName ?? "(unknown)",
          vaultPath: data.vaultPath ?? "",
          vaultExists: Boolean(data.vaultExists),
          vaultSetup: data.vaultSetup ?? "missing",
          acpxPermissionMode: data.acpxPermissionMode ?? "approve-reads",
          preflight: {
            ...defaultPreflight,
            ...pf,
            skillNames: pf?.skillNames ?? [],
            issues: pf?.issues ?? [],
          },
        });
      } catch {
        if (!cancelled) {
          setDesk((d) => ({
            ...d,
            displayName: "(unavailable)",
          }));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const chatId = `acpx:${sessionName}`;

  const bumpRecent = React.useCallback((name: string) => {
    setRecentSessions((prev) => {
      const next = [name, ...prev.filter((s) => s !== name)];
      return next.slice(0, 24);
    });
  }, []);

  const onSessionNameChange = React.useCallback(
    (name: string) => {
      setSessionName(name);
      bumpRecent(name);
    },
    [bumpRecent],
  );

  const onNewChat = React.useCallback(() => {
    const name = randomSessionName();
    setSessionName(name);
    bumpRecent(name);
  }, [bumpRecent]);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-0 overflow-hidden lg:flex-row lg:gap-4 lg:p-4">
      <WorkspaceExplorer
        workspaceLabel={desk.displayName}
        workspacePath={desk.workspacePath}
        vaultPath={desk.vaultPath}
        vaultExists={desk.vaultExists}
        vaultSetup={desk.vaultSetup}
        acpxPermissionMode={desk.acpxPermissionMode}
        preflight={desk.preflight}
        sessionName={sessionName}
        recentSessions={recentSessions}
        onSessionNameChange={onSessionNameChange}
        onNewChat={onNewChat}
      />
      <AgentChatPanel
        sessionName={sessionName}
        chatId={chatId}
        vaultPath={desk.vaultPath}
        vaultExists={desk.vaultExists}
        vaultSetup={desk.vaultSetup}
        acpxPermissionMode={desk.acpxPermissionMode}
        preflight={desk.preflight}
      />
    </div>
  );
}
