import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_SESSION_NAME,
  normalizeSessionName,
} from "@/lib/session-name";

test("normalizes omitted and blank session names to the domain default", () => {
  assert.equal(normalizeSessionName(undefined), DEFAULT_SESSION_NAME);
  assert.equal(normalizeSessionName("   "), DEFAULT_SESSION_NAME);
});

test("rejects session names outside the ACP-safe syntax", () => {
  assert.equal(normalizeSessionName("bad/name"), null);
});
