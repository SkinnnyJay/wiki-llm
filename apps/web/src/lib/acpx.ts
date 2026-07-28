import { spawn, spawnSync } from "node:child_process";
import { createInterface } from "node:readline";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import type { AcpxJsonEvent } from "@/types/acpx";
import { buildFullSystemPrompt, composeAcpxPromptFileBody } from "@/lib/system-prompt";
import type { WikiPreflight } from "@/lib/wiki-preflight";

function npxBinary(): string {
  return process.platform === "win32" ? "npx.cmd" : "npx";
}

function acpxArgs(): string[] {
  const bin = process.env.ACP_ACPX_PACKAGE ?? "acpx@latest";
  return [bin];
}

/**
 * acpx global permission flags (before subcommand). See `acpx --help`.
 * Default `approve-reads`: safer for vault work (auto-approve reads, prompt writes).
 * Set `ACP_ACPX_PERMISSION_MODE=approve-all` or `deny-all` to override.
 */
export function acpxPermissionFlags(): string[] {
  const mode =
    process.env.ACP_ACPX_PERMISSION_MODE?.trim().toLowerCase() ?? "approve-reads";
  if (mode === "approve-all") return ["--approve-all"];
  if (mode === "deny-all") return ["--deny-all"];
  return ["--approve-reads"];
}

export function getWorkspaceDir(): string {
  const w = process.env.ACP_WORKSPACE?.trim();
  if (w) return w;
  return process.cwd();
}

/**
 * Ensure a named Claude (ACP) session exists for the workspace.
 */
export function ensureClaudeSession(workspace: string, sessionName: string): void {
  const args = [
    ...acpxArgs(),
    ...acpxPermissionFlags(),
    "--cwd",
    workspace,
    "claude",
    "sessions",
    "ensure",
    "--name",
    sessionName,
  ];
  const r = spawnSync(npxBinary(), args, {
    encoding: "utf8",
    env: process.env,
  });
  if (r.status !== 0) {
    const err = (r.stderr || r.stdout || "").trim();
    throw new Error(
      err || `acpx claude sessions ensure failed (exit ${r.status ?? "unknown"})`,
    );
  }
}

function extractTextDelta(event: AcpxJsonEvent): string | null {
  const t = event.type;
  if (typeof event.delta === "string" && event.delta.length > 0) {
    return event.delta;
  }
  if (typeof event.text === "string" && event.text.length > 0) {
    return event.text;
  }
  if (t === "tool_call" && typeof event.title === "string") {
    return `\n[tool] ${event.title}${event.status ? ` (${event.status})` : ""}\n`;
  }
  if (t === "thinking" && typeof event.text === "string") {
    return `\n[thinking] ${event.text}\n`;
  }
  const content = event.content;
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    const parts: string[] = [];
    for (const part of content) {
      if (part && typeof part === "object" && "text" in part) {
        const p = part as { text?: unknown };
        if (typeof p.text === "string") parts.push(p.text);
      }
    }
    if (parts.length) return parts.join("");
  }
  return null;
}

/**
 * Stream assistant-facing text extracted from acpx NDJSON (`--format json`).
 * Prepends the Agent desk system prompt from `prompts/` (see `getSystemPromptForTurn`)
 * into the `--file` payload; acpx does not expose a separate `--system` flag.
 */
export async function* streamAcpxClaudePrompt(options: {
  workspace: string;
  sessionName: string;
  prompt: string;
  /** Override merged system prompt (e.g. tests); default loads from prompts/ */
  systemPrompt?: string;
  /** When set, avoids recomputing plugin/skills discovery for the same turn. */
  preflight?: WikiPreflight;
}): AsyncGenerator<string> {
  const { workspace, sessionName, prompt } = options;
  const system =
    options.systemPrompt !== undefined
      ? options.systemPrompt
      : buildFullSystemPrompt(workspace, options.preflight);
  const fileBody = composeAcpxPromptFileBody(system, prompt);
  const dir = await mkdtemp(join(tmpdir(), "acpx-prompt-"));
  const file = join(dir, "prompt.md");
  await writeFile(file, fileBody, "utf8");

  const args = [
    ...acpxArgs(),
    ...acpxPermissionFlags(),
    "--format",
    "json",
    "--cwd",
    workspace,
    "claude",
    "-s",
    sessionName,
    "--file",
    file,
  ];

  const child = spawn(npxBinary(), args, {
    env: process.env,
    stdio: ["ignore", "pipe", "pipe"],
  });

  const stderrChunks: string[] = [];
  child.stderr.setEncoding("utf8");
  child.stderr.on("data", (chunk: string) => {
    stderrChunks.push(chunk);
  });

  const rl = createInterface({ input: child.stdout });
  try {
    for await (const line of rl) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      let parsed: unknown;
      try {
        parsed = JSON.parse(trimmed) as AcpxJsonEvent;
      } catch {
        yield `\n${trimmed}\n`;
        continue;
      }
      const delta = extractTextDelta(parsed as AcpxJsonEvent);
      if (delta) yield delta;
    }
  } finally {
    rl.close();
  }

  const code = await new Promise<number>((resolve) => {
    child.on("close", (c) => resolve(c ?? 0));
  });

  await rm(dir, { recursive: true, force: true });

  if (code !== 0) {
    const tail = stderrChunks.join("").trim();
    throw new Error(
      tail || `acpx exited with code ${code}`,
    );
  }
}
