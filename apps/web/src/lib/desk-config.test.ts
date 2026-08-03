import assert from "node:assert/strict";
import test from "node:test";

import { decodeDeskConfig } from "@/lib/desk-config";

test("rejects a non-object desk configuration response", () => {
  assert.equal(decodeDeskConfig(null), null);
  assert.equal(decodeDeskConfig([]), null);
});

test("uses safe display defaults for a valid minimal desk response", () => {
  const config = decodeDeskConfig({ workspacePath: "/repo" });

  assert.equal(config?.workspacePath, "/repo");
  assert.equal(config?.displayName, "(unknown)");
  assert.equal(config?.vaultSetup, "missing");
  assert.equal(config?.acpxPermissionMode, "approve-reads");
});

test("rejects invalid typed values instead of placing them in component state", () => {
  assert.equal(decodeDeskConfig({ workspacePath: 7 }), null);
  assert.equal(
    decodeDeskConfig({ workspacePath: "/repo", preflight: { skillNames: [7] } }),
    null,
  );
});
