---
name: backlog
description: Manage the project backlog on GitHub (issues, labels, milestones, Project board). Use it to create well-specified bugs/features/tasks, triage and prioritise, audit the backlog quality, link work to PRs so merging closes the issue, plan a release (milestone), or set up the repo's labels/board. Trigger on "create an issue", "add this to the backlog", "what's pending", "prioritise", "plan the next release", "triage", "link the PR to the issue", "set up the project board", and whenever another skill or agent finds a bug or task that should be tracked.
---

# Backlog (GitHub as the single source of truth for pending work)

Pending work lives in **GitHub Issues + the Project board**, not in `CLAUDE.md`. Everything is driven with the `gh` CLI.
Config (repo, project number) is in `.claude/skills/backlog/config.json`. The repository is **public**: see "Public repo rules".

## How the pieces fit

| Piece | Purpose | Where |
|---|---|---|
| **Issue** | One unit of work, fully specified (bug / feature / task) | issue forms in `.github/ISSUE_TEMPLATE/` |
| **Labels** | Type (`bug` `feature` `task` `docs` `security`), priority (`P0`-`P3`), area (`area:*`), flags (`needs-discussion` `blocked` `production` `from-test-report`) | `references/labels.json` |
| **Milestone** | A release (`v1.2.0`): the set of issues that ship together; matches `VERSION` in `globals.py` | GitHub milestones |
| **Project board** | Workflow state: Backlog → Ready → In progress → In review → Done; plus Size | see `references/project-setup.md` |
| **PR** | Implements exactly one issue; body has `Closes #n` | `.github/pull_request_template.md` |

Rule of thumb: labels say **what** it is, milestone says **when it ships**, the board says **where it is now**.

## Lifecycle

1. **Create** (`scripts/issue.py create`, or the web form). Must have type, priority, area and the required sections (below).
2. **Triage**: a maintainer checks it is well defined, sets priority/area, adds `needs-discussion` if a decision is missing, moves it to *Ready* when someone could start without asking questions.
3. **Work**: branch `fix/<name>` or `feature/<name>` off `develop`, named after the issue; move to *In progress*. One issue = one branch = one PR. For a set of related issues use an umbrella branch (see GitFlow in CLAUDE.md); the umbrella PR lists every `Closes #n`.
4. **PR** into `develop` with `Closes #n`. GitHub only auto-closes on merges to the default branch (`master`), so `.github/workflows/close-linked-issues.yml` closes the issues when the PR merges into `develop`. Use `Refs #n` for partial work.
5. **Release**: PR `develop` → `master` with the milestone's issues listed; the milestone is closed after deploy.

## Creating a well-defined issue

Run from the repo root. Write the body to a file (scratchpad), then:

```bash
python .claude/skills/backlog/scripts/issue.py create --type bug --title "Imperative or descriptive, specific" \
  --body-file body.md --priority P1 --area email [--milestone v1.2.0] [--label needs-discussion] [--dry-run]
```

It refuses bodies without the required `### ` sections, flags likely secrets, applies the labels and adds the issue to the board. Required sections:

- **bug**: `Summary`, `Steps to reproduce / evidence`, `Expected vs actual behaviour` (+ recommended `Root cause / affected code`, `Proposed fix and how to verify`)
- **feature**: `Problem / goal`, `Proposed solution and scope`, `Acceptance criteria` (checklist `- [ ]`) (+ `Technical notes and deployment impact`)
- **task**: `Context and goal`, `Plan / checklist`, `Definition of done` (+ `Risks and approvals needed`)

Quality bar (see `references/issue-standards.md`): someone with no context can start work without asking; the title names the symptom or outcome, not the solution; acceptance/definition of done is verifiable; production impact and owner approvals are stated. Split anything bigger than ~1 week or touching several areas into linked issues (`Part of #n`, task lists).

## Everyday commands

```bash
gh issue list --label P0 --state open               # what is urgent (repeat --label for AND)
gh issue list --search 'label:bug label:area:email'
gh issue view 12 --comments
gh issue edit 12 --add-label needs-discussion --milestone v1.2.0
gh issue comment 12 --body "..."
python .claude/skills/backlog/scripts/issue.py audit  # issues missing type/priority/area/sections
gh pr create --base develop --title "fix: ..." --body-file pr.md   # pr.md ends with "Closes #12"
```

## One-time / occasional setup (idempotent)

```bash
python .claude/skills/backlog/scripts/setup_repo.py labels             # create/update the label set
python .claude/skills/backlog/scripts/setup_repo.py settings [--apply]  # delete head branch on merge, merge commits only
python .claude/skills/backlog/scripts/setup_repo.py project [--apply]   # board + Size field (needs: gh auth refresh -s project)
```

`settings` and `project` change the repository: they are dry runs unless `--apply`, and applying needs the owner's OK.

## Public repo rules

The repo is public. Never put in an issue/PR: secrets, tokens, SMTP/DB passwords, customer personal data, raw production logs, hostnames/IPs/ports of servers, or exploit steps. Describe security work generically (e.g. "restrict database port exposure") and keep sensitive specifics in `.claude/servers.local.md` or a private channel. Vulnerabilities go through GitHub's private security advisory, never a public issue.

## Integration with other work

- `test-bug-report` publishes confirmed findings here (asking the user first) and reads open `bug` issues back into `findings.json`.
- Agents that find a bug while doing something else: open an issue (or propose it) instead of fixing it inline; one bug = one `fix/*` branch.
- Agents never merge PRs, push to `master`/`develop`, change repo settings or close issues others opened without the user's explicit confirmation.
