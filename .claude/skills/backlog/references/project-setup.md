# Project board setup (GitHub Projects v2)

The API can create the project, link it to the repo and add custom fields, but **not** edit the built-in Status options nor enable the built-in workflows. Those take 2 minutes in the web UI.

## 1. Token scope (once, interactive)
```
gh auth refresh -s project
```

## 2. Create and link (script)
```
python .claude/skills/backlog/scripts/setup_repo.py project --apply
```
Creates the user project "Booking API", links it to the repository, adds a `Size` field (XS/S/M/L/XL) and writes the project number to `config.json` (commit that file).

## 3. UI steps (Project → ⋯ → Settings)
1. **Status** field: options `Backlog`, `Ready`, `In progress`, `In review`, `Done`.
2. **Workflows** (⋯ → Workflows), enable:
   - *Item added to project* → Status = Backlog
   - *Item closed* → Status = Done
   - *Pull request merged* → Status = Done
   - *Auto-add to project* → filter `is:issue,pr repo:daniieelgs/booking_api` (so UI-created issues land on the board)
3. **Views**: Board grouped by Status; Table "Triage" filtered `no:label` or missing priority; Roadmap by milestone.
4. Make it visible to the team: Settings → Manage access.

## Notes
- Priority and Area are **labels** (filterable in any view with `label:P1`), not custom fields, so they work in issue lists, searches and the CLI too.
- Milestones are releases (`vX.Y.Z`); create one with `gh api repos/daniieelgs/booking_api/milestones -f title=v1.2.0 -f description="..."`.
