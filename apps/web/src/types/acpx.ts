/**
 * Loose typing for acpx NDJSON lines (`--format json`).
 * @see https://github.com/openclaw/acpx
 */
export type AcpxJsonEvent = {
  eventVersion?: number;
  sessionId?: string;
  requestId?: string;
  seq?: number;
  stream?: string;
  type?: string;
  delta?: string;
  text?: string;
  content?: unknown;
  title?: string;
  status?: string;
  [key: string]: unknown;
};
