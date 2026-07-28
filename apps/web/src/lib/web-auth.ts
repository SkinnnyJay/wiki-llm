import { createHash, timingSafeEqual } from "node:crypto";

/**
 * Require `ACP_WEB_TOKEN` on Agent desk API routes.
 * Compare via SHA-256 digests + timingSafeEqual (fixed-length buffers).
 *
 * Clients should send `Authorization: Bearer <token>` or `X-ACP-Web-Token: <token>`.
 * For the browser UI, set `NEXT_PUBLIC_ACP_WEB_TOKEN` to the same value
 * (localhost-only desk — treat the public token as visible to anyone who can
 * load the page; do not bind Next to a non-loopback address).
 */
export function requireWebToken(req: Request): Response | null {
  const hostError = requireLoopbackHost(req);
  if (hostError) return hostError;

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

/** Fail closed if the request Host / X-Forwarded-Host is not loopback. */
export function requireLoopbackHost(req: Request): Response | null {
  const forwarded = req.headers.get("x-forwarded-host")?.split(",")[0]?.trim() ?? "";
  const raw = (forwarded || req.headers.get("host") || "").trim().toLowerCase();
  const host = raw.split(":")[0]?.replace(/^\[|\]$/g, "") ?? "";
  const allowed = new Set(["localhost", "127.0.0.1", "::1"]);
  if (!host || !allowed.has(host)) {
    return jsonError(
      403,
      "Forbidden",
      "Agent desk APIs only accept localhost Host (bind Next to 127.0.0.1).",
    );
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
