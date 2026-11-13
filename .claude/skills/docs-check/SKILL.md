---
name: docs-check
description: Run the documentation consistency checker - verifies that the repo paths mentioned in CLAUDE.md, docs/, agents and skills exist, that relative links resolve, that CLAUDE.md stays within its size budget and has no roadmap, and that agents/skills have valid frontmatter. Use before and after editing documentation, in PRs that touch docs/agents/skills, and when asked "are the docs up to date" or "check the docs".
---

# docs-check

```bash
python .claude/skills/docs-check/scripts/check_docs.py          # report; exit 1 if there are errors
python .claude/skills/docs-check/scripts/check_docs.py --strict # warnings also fail
```

Run from the repo root. Checks (all read-only):

| Check | Level |
|---|---|
| `CLAUDE.md` over the size budget (16 000 bytes) | error |
| `CLAUDE.md` has a "Roadmap"/"pending tasks" section (belongs in the GitHub backlog) | error |
| Backticked repo paths in the docs (for example `resources/<file>.py` or `docs/<file>.md`, `.claude/...`, `scripts/...`) that do not exist | error |
| Relative Markdown links that do not resolve | error |
| Agent/skill file without `name`/`description` frontmatter, or name different from its folder/file | error |
| Mentioned `python ...scripts/*.py` commands whose script does not exist | error |
| Docs mention `VERSION` numbers different from `globals.py` | warning |

The checker finds **broken references only**; it cannot tell whether a sentence is still true. After it passes, spot-check claims against the code (env vars, container names, commands, behaviour), which is what the `docs-keeper` agent does.

Paths that legitimately do not exist in the repo (gitignored or server-only) are listed in `IGNORED` inside the script: `private/`, `public/`, `.env*`, `.claude/servers.local.md`, `migrations/`, `instance/`, `.venv/`.
