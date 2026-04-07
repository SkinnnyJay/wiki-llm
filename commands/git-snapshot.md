---
description: Commit current vault state with a message (vault-scoped git).
---

Ask the user for a commit message, then run:

```bash
llm-wiki git snapshot -m "YOUR_MESSAGE"
```

If `$ARGUMENTS` is non-empty, use it as the message.

Requires `git.enabled` and an initialized vault repository.
