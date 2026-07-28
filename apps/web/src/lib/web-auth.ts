import { createHash, timingSafeEqual } from "node:crypto";

/**
 * Require `ACP_WEB_TOKEN` on Agent desk API routes.
 * Compare via SHA-256 digests + timingSafeEqual (fixed-length buffers).
 *
 * Clients should send `Authorization: Bearer <token>` or `X-ACP-Web-Token: <token>`.
 * For the browser UI, set `NEXT_PUBLIC_ACP_WEB_TOKEN` to the same value.
 */
export function requireWebToken(req: Request): Response | null {
  const expected = process.env.ACP_WEB_TOKEN?.trim() ?? "";
  if (!expected) {
    return jsonError(
      503,
      "ACP_WEB_TOKEN is not configured",
      "Set ACP_WEB_TOKEN in apps/web/.env.local (localhost-only Agent desk).",
    );
  }

  const provided = extractProvidedToken(req);
  if (!provided) {
    return jsonError(
      401,
      "Unauthorized",
      "Missing token. Send Authorization: Bearer <ACP_WEB_TOKEN> or X-ACP-Web-Token.",
    );
  }

  if (!tokensEqual(provided, expected)) {
    return jsonError(401, "Unauthorized", "Invalid ACP_WEB_TOKEN.");
  }

  return null;
}

function extractProvidedToken(req: Request): string {
  const headerToken = req.headers.get("x-acp-web-token")?.trim() ?? "";
  if (headerToken) return headerToken;

  const auth = req.headers.get("authorization")?.trim() ?? "";
  const match = /^Bearer\s+(.+)$/i.exec(auth);
  return match?.[1]?.trim() ?? "";
}

function tokensEqual(a: string, b: string): boolean {
  const ha = createHash("sha256").update(a, "utf8").digest();
  const hb = createHash("sha256").update(b, "utf8").digest();
  return ha.length === hb.length && timingSafeEqual(ha, hb);
}

function jsonError(status: number, error: string, detail: string): Response {
  return new Response(JSON.stringify({ error, detail }), {
    status,
    headers: { "content-type": "application/json" },
  });
}
