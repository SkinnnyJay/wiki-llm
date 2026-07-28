# First-run routing questions

Ask only the questions needed to choose a destination:

1. **Do you already have an `llm-wiki/` vault with `config.json`?**
   - No or unsure → `/llm-wiki:setup`
2. **Are you trying to change settings such as MCP, search, persona, or memory?**
   - Yes → `/llm-wiki:configure`
3. **Is the vault failing, incomplete, or are you unsure it is ready?**
   - Yes → `llm-wiki doctor`
4. **Do you want safe automatic repairs for missing `raw/`/`wiki/` directories or blank non-secret defaults?**
   - Yes → `llm-wiki doctor --fix`

After any destination flow completes, run `llm-wiki doctor` to verify the vault.
