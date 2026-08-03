# Domain Contract and Strictness Design

## Purpose

Keep the local Agent Desk aligned with the llm-wiki plugin's purpose: a
localhost-only interface for a bounded wiki workspace and Claude ACP sessions.
Its public request, session, and preflight contracts must remain explicit,
validated at boundaries, and easy to change without duplicating rules between
the API and UI.

## Scope

The first modernization slice covers the web desk's stable domain vocabulary:

- session identifiers and their display/default values;
- bounded recent-session history and generated session suffixes;
- vault setup and ACP permission states returned by `/api/config`;
- client-side decoding of the `/api/config` response.

It will name the current behavioral limits in one module, replace broad string
fields with the domain unions already produced by the server, and reject an
invalid config response instead of silently treating arbitrary JSON as a desk
configuration. The production smoke test will continue to prove the real API
and default prompt path work together.

## Approach

1. Keep values that cross the server/client boundary in `src/types/desk.ts`.
   That is the desk's contract module, not a generic utility bucket.
2. Keep session syntax and session-history limits in `src/lib/session-name.ts`.
   The module owns the rules for a session name and the UI consumes its named
   constants; the server remains the authoritative validator.
3. Add a small JSON decoder for `/api/config` in the chat client. It accepts
   only the primitive shapes used by the desk, supplies documented safe
   defaults for omitted optional fields, and makes malformed success responses
   visible as an unavailable desk rather than propagating unchecked data.
4. Do not introduce a runtime schema package. The contract is small, uses no
   external input beyond one local API response, and a focused type guard is
   easier to audit than a new dependency.

## Error Handling and Security

- The API remains the security boundary: it authenticates, enforces loopback
  hosting, and validates session names before invoking ACP.
- The client decoder is a resilience boundary, not an authorization mechanism.
- The session module does not expose a mutable regular expression or permit
  arbitrary names; the same normalization is used before UI state changes.

## Testing

- Add focused unit tests for session generation/history constants and config
  decoding edge cases.
- Preserve and run the production HTTP smoke test for authentication and
  malformed chat requests.
- Run TypeScript strict checking, linting, a production build, and the Python
  release suite after the focused changes.

## Deferred Python Modernization

The Python baseline has no basedpyright errors but 1,092 warning-level `Any`
diagnostics. Those originate mostly in the legacy argparse dispatch layer and
optional integration adapters. This is a separate, larger migration: each CLI
subcommand needs a typed argument model and adapters need typed external
payload decoders. The current slice does not weaken diagnostics or hide that
debt; it establishes the same explicit-boundary pattern in the web desk first.
