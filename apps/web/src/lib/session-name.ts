const SESSION_NAME = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;

export const DEFAULT_SESSION_NAME = "web-default";
export const RECENT_SESSION_LIMIT = 24;
export const GENERATED_SESSION_ID_LENGTH = 8;

export const SESSION_NAME_HELP =
  "Use 1-64 letters, numbers, dots, underscores, or hyphens; start with a letter or number.";

/** Normalize a user-visible ACP session name, or reject invalid input. */
export function normalizeSessionName(value: unknown): string | null {
  if (value === undefined) return DEFAULT_SESSION_NAME;
  if (typeof value !== "string") return null;
  const sessionName = value.trim() || DEFAULT_SESSION_NAME;
  return SESSION_NAME.test(sessionName) ? sessionName : null;
}
