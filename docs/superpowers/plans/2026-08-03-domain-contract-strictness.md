# Domain Contract Strictness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Agent Desk's session and configuration contracts explicit,
typed, bounded, and validated at the client boundary without changing the
server's security authority.

**Architecture:** `types/desk.ts` owns stable server/client vocabulary.
`lib/session-name.ts` owns session syntax and all related limits. `types/desk.ts`
also exports `DeskConfig`, and a small local decoder turns `/api/config` JSON
into that type before the chat app renders, keeping unchecked JSON from entering
component state.

**Tech Stack:** Next.js 16, React 19, TypeScript strict mode, ESLint, Node HTTP
smoke test.

## Global Constraints

- Keep the Agent Desk localhost-only and retain API-side token, host, and
  session validation.
- Add no runtime schema dependency for the small local config payload.
- Use named constants for session-related limits and defaults.
- Preserve the existing `/api/config` response shape.

---

### Task 1: Define explicit desk and session contracts

**Files:**
- Modify: `apps/web/src/types/desk.ts`
- Modify: `apps/web/src/lib/session-name.ts`
- Test: `apps/web/src/lib/session-name.test.ts`

**Interfaces:**
- Produces `VaultSetupState`, `AcpxPermissionMode`, `DeskConfig`, `DEFAULT_SESSION_NAME`,
  `RECENT_SESSION_LIMIT`, `GENERATED_SESSION_ID_LENGTH`, and
  `normalizeSessionName(value: unknown): string | null`.

- [ ] **Step 1: Write failing session-rule tests**

```ts
import assert from "node:assert/strict";
import test from "node:test";
import { DEFAULT_SESSION_NAME, normalizeSessionName } from "@/lib/session-name";

test("uses the named default only for omitted or blank session names", () => {
  assert.equal(normalizeSessionName(undefined), DEFAULT_SESSION_NAME);
  assert.equal(normalizeSessionName("   "), DEFAULT_SESSION_NAME);
  assert.equal(normalizeSessionName("bad/name"), null);
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm run test:unit -- session-name.test.ts`

Expected: FAIL because the named constants and unit-test script do not yet
exist.

- [ ] **Step 3: Add the named contract values and replace session literals**

```ts
export const DEFAULT_SESSION_NAME = "default";
export const RECENT_SESSION_LIMIT = 24;
export const GENERATED_SESSION_ID_LENGTH = 8;
```

Use these exports in the session module and `chat-app.tsx`; add the two domain
unions to `types/desk.ts` and use them in `PreflightClient` and `DeskConfig`.

- [ ] **Step 4: Run lint and TypeScript checking**

Run: `npm run lint && npm run typecheck`

Expected: PASS.

### Task 2: Decode the local configuration response before state updates

**Files:**
- Create: `apps/web/src/lib/desk-config.ts`
- Create: `apps/web/src/lib/desk-config.test.ts`
- Modify: `apps/web/src/components/chat-app.tsx`

**Interfaces:**
- Consumes: `PreflightClient`, `VaultSetupState`, and `AcpxPermissionMode`.
- Produces: `decodeDeskConfig(value: unknown): DeskConfig | null`.

- [ ] **Step 1: Write failing decoder tests**

```ts
import assert from "node:assert/strict";
import test from "node:test";
import { decodeDeskConfig } from "@/lib/desk-config";

test("rejects a non-object config response", () => {
  assert.equal(decodeDeskConfig(null), null);
});

test("uses safe defaults for omitted optional desk fields", () => {
  assert.equal(decodeDeskConfig({ workspacePath: "/repo" })?.displayName, "(unknown)");
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm run test:unit -- desk-config.test.ts`

Expected: FAIL because the decoder and unit-test script do not yet exist.

- [ ] **Step 3: Implement the decoder and use it in `ChatApp`**

```ts
const data: unknown = await response.json();
const desk = decodeDeskConfig(data);
if (!desk) throw new Error("Invalid Agent Desk configuration response");
setDesk(desk);
```

The decoder must verify object, string, boolean, string-array, and union
members before returning a `DeskConfig`; unknown optional values use the same
safe defaults as the current UI.

- [ ] **Step 4: Run unit, lint, and type checks**

Run: `npm run test:unit && npm run lint && npm run typecheck`

Expected: PASS.

### Task 3: Release verification

**Files:**
- Modify: `apps/web/package.json`
- Modify: `.github/workflows/tests.yml`

**Interfaces:**
- Consumes: unit test command from Tasks 1 and 2.
- Produces: CI coverage for web unit tests in addition to lint, typecheck,
  build, and HTTP smoke.

- [ ] **Step 1: Add the focused unit-test command to the web package**

```json
"test:unit": "tsx --test src/lib/*.test.ts"
```

Add `tsx` as the smallest development dependency necessary to execute the
focused Node test files, updating the lockfile. Do not add a second assertion
or test framework: tests use `node:test` and `node:assert/strict`.

- [ ] **Step 2: Add the web unit test command to CI before the build**

```yaml
- name: Unit tests
  run: npm run test:unit
```

- [ ] **Step 3: Run all web gates**

Run: `npm run test:unit && npm run lint && npm run typecheck && npm run build && npm run test:http`

Expected: PASS with no production-build warnings.

- [ ] **Step 4: Run repository regression gates**

Run: `python3 -m pytest -q`, `ruff check scripts tests`, and
`bin/llm-wiki test-report`

Expected: all pass with no failures.
