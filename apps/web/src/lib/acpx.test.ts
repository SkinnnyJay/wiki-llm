import assert from "node:assert/strict";
import test from "node:test";

import { getAcpxPermissionMode } from "@/lib/acpx";

test("normalizes ACP permission modes to the supported domain values", () => {
  assert.equal(getAcpxPermissionMode(undefined), "approve-reads");
  assert.equal(getAcpxPermissionMode("approve-all"), "approve-all");
  assert.equal(getAcpxPermissionMode("DENY-ALL"), "deny-all");
});

test("fails closed to read approval for an unsupported ACP permission mode", () => {
  assert.equal(getAcpxPermissionMode("unsafe-everything"), "approve-reads");
});
