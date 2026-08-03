import {
  createUIMessageStream,
  createUIMessageStreamResponse,
} from "ai";
import type { UIMessage } from "ai";

import { ensureClaudeSession, getWorkspaceDir, streamAcpxClaudePrompt } from "@/lib/acpx";
import { lastUserText } from "@/lib/chat-request";
import { normalizeSessionName } from "@/lib/session-name";
import { getSystemPromptForTurn } from "@/lib/system-prompt";
import { requireWebToken } from "@/lib/web-auth";
import {
  computeWikiPreflight,
  preflightForClient,
  skipSkillPreflightGate,
} from "@/lib/wiki-preflight";

export const runtime = "nodejs";
export const maxDuration = 300;

type ChatRequestBody = {
  messages?: unknown;
  sessionName?: unknown;
};

function badRequest(error: string): Response {
  return new Response(JSON.stringify({ error }), {
    status: 400,
    headers: { "content-type": "application/json" },
  });
}

function isChatMessages(value: unknown): value is UIMessage[] {
  return Array.isArray(value) && value.every((message) => {
    if (!message || typeof message !== "object") return false;
    const candidate = message as { role?: unknown; parts?: unknown };
    return typeof candidate.role === "string" && Array.isArray(candidate.parts);
  });
}

export async function POST(req: Request) {
  const authError = requireWebToken(req);
  if (authError) return authError;

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return badRequest("Invalid JSON request body");
  }
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return badRequest("Invalid request body");
  }
  const requestBody = body as ChatRequestBody;
  if (!isChatMessages(requestBody.messages)) {
    return badRequest("Invalid messages array");
  }
  const sessionName = normalizeSessionName(requestBody.sessionName);
  if (!sessionName) {
    return badRequest("Invalid session name");
  }
  const prompt = lastUserText(requestBody.messages);
  if (!prompt) {
    return badRequest("Missing user message");
  }

  try {
    getSystemPromptForTurn();
  } catch (e) {
    const detail = e instanceof Error ? e.message : String(e);
    return new Response(
      JSON.stringify({
        error: "System prompt unavailable",
        detail,
      }),
      {
        status: 500,
        headers: { "content-type": "application/json" },
      },
    );
  }

  const workspace = getWorkspaceDir();
  const preflight = computeWikiPreflight(workspace);

  if (!preflight.readyForClaude && !skipSkillPreflightGate()) {
    return new Response(
      JSON.stringify({
        error: "wiki-llm skills not available",
        detail:
          "The server could not find the plugin checkout (skills/wiki-setup/SKILL.md). Set LLM_WIKI_PLUGIN_ROOT to the wiki-llm repo root, or point ACP_WORKSPACE inside that repo. Override: ACP_WEB_SKIP_SKILL_CHECK=1",
        preflight: preflightForClient(preflight),
      }),
      {
        status: 503,
        headers: { "content-type": "application/json" },
      },
    );
  }

  const stream = createUIMessageStream({
    originalMessages: requestBody.messages,
    execute: async ({ writer }) => {
      const id = crypto.randomUUID();
      writer.write({ type: "text-start", id });
      try {
        ensureClaudeSession(workspace, sessionName);
        for await (const delta of streamAcpxClaudePrompt({
          workspace,
          sessionName,
          prompt,
          preflight,
        })) {
          if (delta) {
            writer.write({ type: "text-delta", id, delta });
          }
        }
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        writer.write({
          type: "text-delta",
          id,
          delta: `\n\n[error] ${msg}\n`,
        });
      } finally {
        writer.write({ type: "text-end", id });
      }
    },
  });

  return createUIMessageStreamResponse({ stream });
}
