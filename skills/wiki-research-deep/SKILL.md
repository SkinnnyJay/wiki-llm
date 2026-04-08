---
name: wiki-research-deep
description: Multi-pass research — runs sub-skills in sequence, writes synthesis draft to outputs/, merges into wiki/ after review gate. For broad/complex topics.
user-invocable: false
context: fork
agent: research-runner
effort: high
---

# Wiki research — deep

Orchestrates a multi-pass research session for broad, complex, or high-stakes topics. Runs multiple sub-skills in sequence, collects evidence into `raw/`, writes an intermediate synthesis draft to `outputs/`, then merges into `wiki/` after a review gate.

Use this sub-skill when:
- The topic requires 3+ independent sources or perspectives.
- The user asks for "comprehensive", "deep research", "full overview", or "everything about X".
- A single fetch would leave major gaps.

---

## Step 1 — Scope the research question

Restate the topic as a single precise research question. If `$ARGUMENTS` is vague, clarify with the user or infer from context.

Example: "What is the current state of LLM reasoning benchmarks?" → precise question: "What benchmarks exist for evaluating LLM reasoning, what are their methodologies, and what are the leading model scores as of 2026?"

Define success criteria: what would "done" look like? (A wiki page with N sections? A synthesis covering X, Y, Z angles?)

---

## Step 2 — Plan the research passes

Decompose the question into 2–4 sub-questions, each mapped to a sub-skill:

| Sub-question | Sub-skill |
|-------------|-----------|
| What papers / formal research exists? | wiki-research-academic |
| What do practitioners say? (blogs, docs) | wiki-research-web |
| What is the current community discussion? | wiki-research-social |
| What is the latest news? | wiki-research-news |

Write this plan to `outputs/research-plan-<topic-slug>.md` before starting:

```markdown
# Research plan: <topic>

**Question:** <precise question>
**Success criteria:** <what done looks like>

## Passes
1. Academic — query: "<arXiv/Semantic Scholar query>"
2. Web — URLs: [<list>]
3. Social — HN search: "<query>"; Twitter: "<query>"
4. News — Perplexity: "<query>"

## Output path
outputs/research-<topic-slug>.md
```

---

## Step 3 — Execute passes in order

Run each sub-skill sequentially. Do not skip to synthesis before all passes are complete.

**Pass 1 — Academic (if applicable):**
```
Invoke wiki-research-academic with the academic sub-question.
Collect raw/ paths from output.
```

**Pass 2 — Web:**
```
Invoke wiki-research-web with relevant URLs or discovered links.
Collect raw/ paths from output.
```

**Pass 3 — Social (if applicable):**
```
Invoke wiki-research-social with HN/Twitter queries.
Collect raw/ paths from output.
```

**Pass 4 — News (if applicable):**
```
Invoke wiki-research-news with recency query.
Collect raw/ paths from output.
```

After each pass, run `skills/wiki-research/references/source-eval.md` on new files. Drop sources that fail the minimum quality bar before synthesis.

**Stop if you have enough:** If 2 passes provide sufficient coverage (5+ high-quality sources), skip remaining passes and proceed to synthesis. More passes ≠ better synthesis.

---

## Step 4 — Write intermediate synthesis draft

Write to `outputs/research-<topic-slug>.md`. Follow `skills/wiki-research/references/synthesis.md` for structure.

Template:
```markdown
---
title: "Research synthesis: <topic>"
status: draft
created: YYYY-MM-DD
sources:
  - raw/academic/...
  - raw/research/...
  - raw/social/...
  - raw/news/...
---

# <Topic>

## Research Question
<precise question>

## Summary
<3–5 sentence executive summary of findings>

## Key Findings
- Finding 1 — `raw/path/file.md`
- Finding 2 — `raw/path/file.md`

## Detailed Analysis

### <Angle 1: e.g. Academic Research>
<synthesis of academic sources>

### <Angle 2: e.g. Practitioner Perspective>
<synthesis of web/blog sources>

### <Angle 3: e.g. Community Discussion>
<synthesis of social sources>

## Contradictions and Open Questions
- <Source A says X; Source B says Y — unresolved>
- <Question not answered by any source>

## Further Research
- <Suggested follow-up queries>

## Sources
| File | Type | Quality |
|------|------|---------|
| raw/... | academic | 5/5 |
```

---

## Step 5 — Review gate

Before promoting to `wiki/`, verify:

```
[ ] All key findings have raw/ citations
[ ] No prompt-injection content quoted verbatim
[ ] Contradictions are surfaced, not silently resolved
[ ] Draft reads coherently as a standalone document
[ ] Length is appropriate (500–2000 words for most topics)
[ ] No hallucinated claims (every assertion traces to a source)
```

If any check fails, fix the draft before proceeding. If uncertain about a claim, mark it `[UNVERIFIED]` and note the gap.

Ask the user to review if:
- The synthesis involves contested claims.
- The scope expanded significantly beyond the original question.
- Sources strongly contradict each other without a clear resolution.

---

## Step 6 — Promote to wiki/

After the review gate passes:

1. Copy or move the draft: `outputs/research-<slug>.md` → `wiki/topics/<slug>.md`
2. Apply wiki formatting: add `[[wikilinks]]`, update `wiki/index.md`
3. Follow hub-and-spoke split if page > 30s reading time (see `synthesis.md`)
4. Append `wiki/log.md`:
   ```
   ## [YYYY-MM-DD] deep-research | <topic>
   - Passes: academic, web, social, news
   - Sources ingested: <count> files in raw/
   - Wiki pages created/updated: <list>
   - Open questions: <any unresolved gaps>
   ```

---

## Step 7 — Return to orchestrator

Notify **wiki-research** that deep research is complete. The orchestrator's post-process step (Step 3) handles `wiki-ingest` and `wiki-maintainer` — do not call them again here.

---

## Scope Control

Deep research can expand indefinitely. Enforce these limits:
- **Max 3 sub-skills per session** without user check-in.
- **Max 20 raw files total** across all passes.
- **Max 2000 words** in the synthesis draft; split into hub+spokes if more is needed.
- **Time budget**: if a pass is taking too long, skip it and note the gap.

---

## Done looks like

- Research plan file under **`outputs/`** (when used); passes executed within scope limits; synthesis draft in **`outputs/`** with citations; review gate passed or user consulted.
- Promotion to **`wiki/`** (if any) updates **`wiki/index.md`** and **`wiki/log.md`**; orchestrator post-process not duplicated.

## Related skills

- **wiki-research** — orchestrator that invoked this skill
- **wiki-research-web** — web pass
- **wiki-research-academic** — academic pass
- **wiki-research-social** — community pass
- **wiki-research-news** — recency pass
- `skills/wiki-research/references/synthesis.md` — synthesis structure guide
- `skills/wiki-research/references/source-eval.md` — source quality scoring

## Smoke check

- **CLI:** Run `llm-wiki integrations status` and any `llm-wiki` line from Step 1 of this skill (from the vault root).
- **Prompt:** Invoke this skill by name in Claude Code; complete Step 1 only and confirm expected CLI or file output.

