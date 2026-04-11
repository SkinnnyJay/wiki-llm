"use client";

import * as React from "react";
import {
  BookOpen,
  FolderGit2,
  Layers,
  MessageSquarePlus,
  Search,
  Sparkles,
} from "lucide-react";

import type { PreflightClient } from "@/types/desk";

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";

export function WorkspaceExplorer({
  workspaceLabel,
  workspacePath,
  vaultPath,
  vaultExists,
  vaultSetup,
  acpxPermissionMode,
  preflight,
  sessionName,
  recentSessions,
  onSessionNameChange,
  onNewChat,
  className,
}: {
  workspaceLabel: string;
  workspacePath: string;
  vaultPath: string;
  vaultExists: boolean;
  vaultSetup: string;
  acpxPermissionMode: string;
  preflight: PreflightClient;
  sessionName: string;
  recentSessions: string[];
  onSessionNameChange: (name: string) => void;
  onNewChat: () => void;
  className?: string;
}) {
  const [query, setQuery] = React.useState("");

  const filtered = recentSessions.filter((s) => {
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return s.toLowerCase().includes(q);
  });

  return (
    <aside
      className={cn(
        "flex h-full min-h-0 w-full shrink-0 flex-col overflow-hidden rounded-none border-b bg-card/85 shadow-sm backdrop-blur-md lg:h-auto lg:w-[min(100%,22rem)] lg:rounded-2xl lg:border lg:border-border/80",
        className,
      )}
    >
      <div className="flex items-center gap-2 border-b border-border/60 px-4 py-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <Sparkles className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold tracking-tight">
            wiki-llm desk
          </div>
          <div className="truncate text-xs text-muted-foreground">
            {workspaceLabel}
          </div>
        </div>
        <Badge variant="secondary" className="shrink-0 font-mono text-[10px]">
          acpx
        </Badge>
      </div>

      <div className="space-y-2 px-4 py-3">
        <div className="rounded-xl border border-border/70 bg-muted/40 p-3 text-xs leading-relaxed">
          <div className="mb-1.5 flex items-center gap-2 font-medium text-foreground">
            <BookOpen className="h-3.5 w-3.5 shrink-0" />
            Vault
          </div>
          {vaultPath ? (
            <>
              <p
                className="break-all font-mono text-[11px] text-muted-foreground"
                title={vaultPath}
              >
                {vaultPath}
              </p>
              <div className="mt-2 flex items-center gap-2">
                <span
                  className={cn(
                    "inline-block size-2 rounded-full",
                    vaultExists ? "bg-emerald-500" : "bg-amber-500",
                  )}
                  aria-hidden
                />
                <span className="text-muted-foreground">
                  {vaultExists
                    ? "Vault path exists"
                    : "Not found — run llm-wiki setup"}
                </span>
              </div>
            </>
          ) : (
            <p className="text-muted-foreground">Resolving vault…</p>
          )}
          {workspacePath ? (
            <p
              className="mt-2 border-t border-border/50 pt-2 font-mono text-[10px] text-muted-foreground/90"
              title={workspacePath}
            >
              cwd: {workspacePath}
            </p>
          ) : null}
          <div className="mt-2 flex flex-wrap items-center gap-2 border-t border-border/50 pt-2">
            <span className="text-muted-foreground">Setup:</span>
            <Badge
              variant="outline"
              className={cn(
                "text-[10px] font-normal",
                vaultSetup === "ready" &&
                  "border-emerald-500/50 text-emerald-800 dark:text-emerald-200",
                vaultSetup === "incomplete" && "border-amber-500/50",
              )}
            >
              {vaultSetup}
            </Badge>
          </div>
        </div>

        <div className="rounded-xl border border-border/70 bg-muted/40 p-3 text-xs leading-relaxed">
          <div className="mb-1.5 flex items-center gap-2 font-medium text-foreground">
            <Layers className="h-3.5 w-3.5 shrink-0" />
            Skills (wiki-llm)
          </div>
          {preflight.skillsReady && preflight.pluginRoot ? (
            <>
              <p className="break-all font-mono text-[10px] text-muted-foreground">
                {preflight.pluginRoot}
              </p>
              <p className="mt-1.5 text-muted-foreground">
                <span className="font-semibold text-foreground">
                  {preflight.skillCount}
                </span>{" "}
                skills loaded
                {preflight.skillsResolvedFrom ? (
                  <span className="text-muted-foreground">
                    {" "}
                    ({preflight.skillsResolvedFrom})
                  </span>
                ) : null}
              </p>
              <p className="mt-1.5 line-clamp-4 text-[11px] leading-snug text-muted-foreground">
                {preflight.skillNames.slice(0, 12).join(" · ")}
                {preflight.skillCount > 12 ? " · …" : ""}
              </p>
            </>
          ) : (
            <p className="text-amber-800 dark:text-amber-200">
              Not found. Set{" "}
              <span className="font-mono">LLM_WIKI_PLUGIN_ROOT</span> to the
              wiki-llm repo or run the app with{" "}
              <span className="font-mono">ACP_WORKSPACE</span> inside that
              checkout.
            </p>
          )}
        </div>

        <Button className="w-full justify-start gap-2" onClick={onNewChat}>
          <MessageSquarePlus className="h-4 w-4" />
          New chat thread
        </Button>
        <Button
          variant="outline"
          className="w-full justify-start gap-2"
          onClick={() => {
            const name = window.prompt(
              "Session name (parallel acpx -s …)",
              sessionName,
            );
            if (name && name.trim()) onSessionNameChange(name.trim());
          }}
        >
          <FolderGit2 className="h-4 w-4" />
          Rename session
        </Button>
      </div>

      <div className="px-4 pb-2">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search threads…"
            className="pl-9"
            aria-label="Search threads"
          />
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
          <span>
            Session:{" "}
            <span className="font-mono text-foreground">{sessionName}</span>
          </span>
          <Badge variant="outline" className="font-mono text-[10px] font-normal">
            {acpxPermissionMode}
          </Badge>
        </div>
      </div>

      <Separator />

      <ScrollArea className="min-h-0 flex-1 px-2">
        <div className="py-2">
          <div className="px-2 pb-2 text-xs font-medium text-muted-foreground">
            Recent threads
          </div>
          <div className="space-y-1">
            {filtered.length === 0 ? (
              <div className="px-2 pb-3 text-xs text-muted-foreground">
                Start a thread to see it listed here.
              </div>
            ) : (
              filtered.map((s) => (
                <button
                  key={s}
                  type="button"
                  className={cn(
                    "w-full rounded-lg px-2 py-2.5 text-left text-sm transition-colors hover:bg-accent",
                    s === sessionName && "bg-accent",
                  )}
                  onClick={() => onSessionNameChange(s)}
                >
                  <div className="font-medium">{s}</div>
                  <div className="text-xs text-muted-foreground">
                    Claude Code via acpx
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      </ScrollArea>

      <div className="border-t border-border/60 px-4 py-3 text-[11px] leading-relaxed text-muted-foreground">
        Claude Code runs via{" "}
        <a
          className="font-medium text-foreground underline underline-offset-4 hover:text-primary"
          href="https://github.com/openclaw/acpx"
          target="_blank"
          rel="noreferrer"
        >
          acpx
        </a>
        . Set <span className="font-mono">ACP_WORKSPACE</span> to your repo;
        <span className="font-mono">LLM_WIKI_VAULT</span>,{" "}
        <span className="font-mono">LLM_WIKI_PLUGIN_ROOT</span>.
      </div>
    </aside>
  );
}
