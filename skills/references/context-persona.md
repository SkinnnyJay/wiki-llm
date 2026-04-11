# Optional persona context (skills)

**Do not paste the full persona into each `SKILL.md`.** Skills should **reference** the canonical file **`prompts/PERSONA.md`** (and optionally this doc) so the agent loads the same voice everywhere. Copying long persona text into skills drifts and duplicates.

When a skill invokes **tools** (bash, file writes, web fetch, subagents) and tone or epistemic stance matters, follow this chain:

1. Read **`prompts/PERSONA.md`** in the llm-wiki plugin repo (warm librarian-robot voice: evidence-first, no fluff, verify don’t trust, iterate).
2. Read **`llm-wiki/config.json` → `persona.name`** (default **Gennie**) — use this as the **display name** for the wiki when naming outputs or addressing the user in skill-owned text.
3. If the task matches **`wiki-librarian`** or **`research-runner`**, also read **`agents/<name>.md`** (e.g. `agents/wiki-librarian.md`) for role-specific emphasis.

Keep injections **short** (a few sentences of operational rules), not the full files — unless the user asks for deep alignment.

Do **not** treat persona as permission to invent facts; it only shapes **how** you report uncertainty and **how** you prioritize verification.
