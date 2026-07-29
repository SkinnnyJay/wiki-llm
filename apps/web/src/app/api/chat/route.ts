import {
  createUIMessageStream,
  createUIMessageStreamResponse,
} from "ai";

import { ensureClaudeSession, getWorkspaceDir, streamAcpxClaudePrompt } from "@/lib/acpx";
import { lastUserText } from "@/lib/chat-request";
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
  messages?: Parameters<typeof lastUserText>[0];
  sessionName?: string;
};

export async function POST(req: Request) {
  const authError = requireWebToken(req);
  if (authError) return authError;

  const body = (await req.json()) as ChatRequestBody;
  if (!body.messages || !Array.isArray(body.messages)) {
    return new Response(JSON.stringify({ error: "Missing messages array" }), {
      status: 400,
      headers: { "content-type": "application/json" },
    });
  }
  const sessionName = (body.sessionName ?? "web-default").trim() || "web-default";
  const prompt = lastUserText(body.messages);
  if (!prompt) {
    return new Response(JSON.stringify({ error: "Missing user message" }), {
      status: 400,
      headers: { "content-type": "application/json" },
    });
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
    originalMessages: body.messages,
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
