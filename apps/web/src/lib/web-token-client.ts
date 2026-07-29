/** Browser-side token for Agent desk API auth (must match server ACP_WEB_TOKEN). */
export function getClientWebToken(): string {
  return process.env.NEXT_PUBLIC_ACP_WEB_TOKEN?.trim() ?? "";
}

/** Headers for same-origin fetch to /api/chat and /api/config. */
export function webAuthHeaders(): Record<string, string> {
  const token = getClientWebToken();
  if (!token) return {};
  return {
    Authorization: `Bearer ${token}`,
    "X-ACP-Web-Token": token,
  };
}
