"use client";

import * as React from "react";

import { AgentChatPanel } from "@/components/agent-chat-panel";
import { WorkspaceExplorer } from "@/components/workspace-explorer";
import { DEFAULT_DESK_CONFIG, decodeDeskConfig } from "@/lib/desk-config";
import {
  DEFAULT_SESSION_NAME,
  GENERATED_SESSION_ID_LENGTH,
  RECENT_SESSION_LIMIT,
} from "@/lib/session-name";
import { webAuthHeaders } from "@/lib/web-token-client";
import type { DeskConfig } from "@/types/desk";

function randomSessionName() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `thread-${crypto.randomUUID().slice(0, GENERATED_SESSION_ID_LENGTH)}`;
  }
  return `thread-${Math.random().toString(16).slice(2, 2 + GENERATED_SESSION_ID_LENGTH)}`;
}

export function ChatApp() {
  const [desk, setDesk] = React.useState<DeskConfig>(DEFAULT_DESK_CONFIG);
  const [sessionName, setSessionName] = React.useState(DEFAULT_SESSION_NAME);
  const [recentSessions, setRecentSessions] = React.useState<string[]>([
    DEFAULT_SESSION_NAME,
  ]);

  React.useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await fetch("/api/config", {
          method: "GET",
          headers: webAuthHeaders(),
        });
        const data: unknown = await res.json();
        const nextDesk = decodeDeskConfig(data);
        if (!nextDesk) {
          throw new Error("Invalid Agent Desk configuration response");
        }
        if (cancelled) return;
        setDesk(nextDesk);
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
      return next.slice(0, RECENT_SESSION_LIMIT);
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
