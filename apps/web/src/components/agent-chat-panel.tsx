"use client";

import * as React from "react";
import type { UIMessage } from "ai";
import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
import { AlertTriangle, Bot, Sparkles } from "lucide-react";

import {
  Conversation,
  ConversationContent,
  ConversationEmptyState,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import {
  Message,
  MessageContent,
  MessageResponse,
} from "@/components/ai-elements/message";
import {
  PromptInput,
  PromptInputFooter,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputTools,
} from "@/components/ai-elements/prompt-input";
import type { PromptInputMessage } from "@/components/ai-elements/prompt-input";
import { Suggestion } from "@/components/ai-elements/suggestion";
import type { PreflightClient } from "@/types/desk";
import { Badge } from "@/components/ui/badge";
import { getTextFromUIMessage } from "@/lib/chat-request";
import { cn } from "@/lib/utils";

const STARTERS = [
  "Using wiki-status, what should I check before research?",
  "Walk wiki-pipeline for my vault from raw/ through validate.",
  "How do wiki-learn and .agent-memory.md fit into daily use?",
  "How do I run `llm-wiki validate` on this vault?",
];

export function AgentChatPanel({
  sessionName,
  chatId,
  vaultPath,
  vaultExists,
  vaultSetup,
  acpxPermissionMode,
  preflight,
  className,
}: {
  sessionName: string;
  chatId: string;
  vaultPath: string;
  vaultExists: boolean;
  vaultSetup: string;
  acpxPermissionMode: string;
  preflight: PreflightClient;
  className?: string;
}) {
  const canSend = preflight.chatAllowed;

  const transport = React.useMemo(
    () =>
      new DefaultChatTransport({
        api: "/api/chat",
        prepareSendMessagesRequest: ({ id, messages, body }) => ({
          body: {
            ...(body ?? {}),
            id,
            messages,
            sessionName,
          },
        }),
      }),
    [sessionName],
  );

  const { messages, sendMessage, status, stop, error } = useChat({
    id: chatId,
    transport,
  });

  const busy = status === "streaming" || status === "submitted";

  const handlePromptSubmit = React.useCallback(
    async (message: PromptInputMessage) => {
      if (!canSend) return;
      const text = message.text.trim();
      if (!text && !(message.files?.length)) return;
      if (message.files?.length) {
        await sendMessage({ text: text || "See attached files." });
        return;
      }
      await sendMessage({ text });
    },
    [sendMessage, canSend],
  );

  const sendStarter = React.useCallback(
    (s: string) => {
      if (!canSend) return;
      void sendMessage({ text: s });
    },
    [sendMessage, canSend],
  );

  return (
    <section
      className={cn(
        "flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-none border-0 bg-card/90 shadow-none backdrop-blur-sm lg:rounded-2xl lg:border lg:border-border/80 lg:shadow-sm",
        className,
      )}
    >
      {!preflight.readyForClaude && !preflight.skillGateSkipped ? (
        <div className="flex shrink-0 items-start gap-2 border-b border-amber-500/40 bg-amber-500/10 px-4 py-2.5 text-sm text-amber-950 dark:text-amber-100">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
          <div>
            <p className="font-medium">Plugin skills required before Claude runs</p>
            <p className="text-xs opacity-90">
              Set{" "}
              <span className="font-mono">LLM_WIKI_PLUGIN_ROOT</span> to the
              wiki-llm repo root, or set{" "}
              <span className="font-mono">ACP_WORKSPACE</span> inside that
              checkout. Emergency override:{" "}
              <span className="font-mono">ACP_WEB_SKIP_SKILL_CHECK=1</span>.
            </p>
          </div>
        </div>
      ) : null}
      {!preflight.readyForClaude && preflight.skillGateSkipped ? (
        <div className="shrink-0 border-b border-border/60 bg-muted/50 px-4 py-2 text-xs text-muted-foreground">
          <span className="font-mono">ACP_WEB_SKIP_SKILL_CHECK=1</span> — server
          will start Claude without verifying local{" "}
          <span className="font-mono">skills/</span>; prompts will lack the
          installed skill list.
        </div>
      ) : null}

      <header className="shrink-0 border-b border-border/60 bg-card/50 px-4 py-3">
        <div className="mx-auto flex max-w-3xl flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2.5">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
                <Sparkles className="h-5 w-5 text-primary" />
              </div>
              <div>
                <h1 className="text-base font-semibold tracking-tight">
                  wiki-llm agent
                </h1>
                <p className="text-sm text-muted-foreground">
                  Research · ingest · build · learn — same skills as the CLI
                </p>
              </div>
            </div>
            {vaultPath && !vaultExists ? (
              <div className="mt-2">
                <Badge
                  variant="outline"
                  className="border-amber-500/50 text-amber-800 dark:text-amber-200"
                >
                  Vault folder not found — run{" "}
                  <span className="font-mono">llm-wiki setup</span> or set{" "}
                  <span className="font-mono">LLM_WIKI_VAULT</span>
                </Badge>
              </div>
            ) : null}
            {vaultSetup !== "ready" && vaultExists ? (
              <div className="mt-2">
                <Badge variant="outline" className="text-xs font-normal">
                  Vault setup: {vaultSetup} — finish wiki-setup when ready
                </Badge>
              </div>
            ) : null}
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <Badge
              variant={busy ? "default" : "secondary"}
              title={
                canSend && !preflight.readyForClaude
                  ? "ACP_WEB_SKIP_SKILL_CHECK=1"
                  : undefined
              }
            >
              {busy ? "Running" : !canSend ? "Blocked" : "Ready"}
            </Badge>
            <Badge variant="outline" className="font-mono text-xs font-normal">
              {acpxPermissionMode}
            </Badge>
            <Badge
              variant="outline"
              className="hidden max-w-[12rem] truncate font-mono text-xs font-normal sm:inline-flex"
              title={sessionName}
            >
              {sessionName}
            </Badge>
          </div>
        </div>
      </header>

      <div className="relative flex min-h-0 flex-1 flex-col bg-muted/20">
        <Conversation className="min-h-0 flex-1">
          <ConversationContent className="mx-auto w-full max-w-3xl gap-5 px-4 py-6">
            {messages.length === 0 ? (
              <ConversationEmptyState
                className="py-6"
                description="Use the same workflows as the plugin: wiki-status, wiki-pipeline, wiki-research, wiki-fetch, wiki-ingest, wiki-lint, wiki-learn, and more. Each turn includes your vault path and installed skill names. Claude runs through acpx on this machine."
                icon={<Bot className="size-10 opacity-70" />}
                title="Build and research your wiki"
              />
            ) : (
              messages.map((m: UIMessage) => {
                const text = getTextFromUIMessage(m);
                if (m.role === "system") {
                  return (
                    <Message key={m.id} from="assistant">
                      <MessageContent className="border border-dashed bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
                        {text}
                      </MessageContent>
                    </Message>
                  );
                }
                return (
                  <Message key={m.id} from={m.role}>
                    <MessageContent>
                      {m.role === "assistant" ? (
                        <MessageResponse>{text}</MessageResponse>
                      ) : (
                        <span className="whitespace-pre-wrap">{text}</span>
                      )}
                    </MessageContent>
                  </Message>
                );
              })
            )}
            {error ? (
              <div className="rounded-lg border border-destructive/40 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                {error.message}
              </div>
            ) : null}
          </ConversationContent>
          <ConversationScrollButton />
        </Conversation>

        <div className="shrink-0 border-t border-border/60 bg-card/90 px-4 py-4 backdrop-blur supports-[backdrop-filter]:bg-card/75">
          <div className="mx-auto w-full max-w-3xl space-y-3">
            <div className="flex flex-wrap gap-2">
              {STARTERS.map((label) => (
                <Suggestion
                  key={label}
                  suggestion={label}
                  onClick={() => sendStarter(label)}
                  variant="outline"
                  disabled={!canSend}
                  className="max-w-full whitespace-normal text-left text-xs leading-snug disabled:pointer-events-none disabled:opacity-40"
                />
              ))}
            </div>

            <PromptInput
              className={cn(
                "rounded-2xl border border-border/80 bg-background shadow-sm",
                !canSend && "pointer-events-none opacity-60",
              )}
              onSubmit={handlePromptSubmit}
            >
              <PromptInputTextarea
                disabled={!canSend}
                placeholder={
                  canSend
                    ? "Ask using wiki-llm skills (vault, research, ingest…)…"
                    : "Resolve plugin skills first (see banner)…"
                }
              />
              <PromptInputFooter>
                <PromptInputTools>
                  <span className="text-muted-foreground text-xs">
                    Enter send · Shift+Enter newline
                  </span>
                </PromptInputTools>
                <PromptInputSubmit
                  onStop={() => void stop()}
                  status={status}
                />
              </PromptInputFooter>
            </PromptInput>
          </div>
        </div>
      </div>
    </section>
  );
}
