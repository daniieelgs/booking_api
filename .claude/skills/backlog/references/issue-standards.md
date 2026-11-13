# Issue standards

## Priority
- **P0**: production down, bookings failing, data loss or a live security leak. Hotfix flow; needs the owner now.
- **P1**: customer-visible risk or a guarantee we promise (e.g. every booking gets its email) at risk; do next.
- **P2**: normal planned work.
- **P3**: nice to have / cleanup; do when idle.

## Type
- **bug**: behaviour differs from the documented/expected one. Needs reproduction or evidence (failing test id, request, redacted log).
- **feature**: new capability with business value. Needs acceptance criteria.
- **task**: operational/infra/refactor/housekeeping with no new user-facing behaviour. Needs a checklist and a definition of done.
- `docs` and `security` are extra labels combined with a type (e.g. `task` + `security`).

## Title
Specific and searchable. Bug: the symptom ("Closed-day check lets a worker read another local's data"). Feature/task: the outcome ("Back up the database nightly with binlog PITR"). No "fix:" prefixes (commits and PRs use Conventional Commits, issues do not).

## Good body checklist
- [ ] Why it matters (who is affected, business or technical impact)
- [ ] Evidence or current state (test ids, `file:line`, redacted logs)
- [ ] Scope: what is in and what is explicitly out
- [ ] Verifiable acceptance criteria / definition of done (including the regression test for bugs)
- [ ] Deployment impact: restart, migration, rebuild, env vars, owner approval, maintenance window
- [ ] Links: `Part of #n`, `Blocked by #n`, related findings (`F-012`)

## Sizing (board field)
XS < 1 h, S half a day, M 1-2 days, L about a week, XL must be split.

## Discussion needed
If a decision is missing (design, data model, business rule, cross-cutting convention), add `needs-discussion`, write the question and the options in the issue, and do not start coding until it is answered.

## Closing
Issues close through the PR (`Closes #n`). Closing without a PR (won't fix, duplicate, obsolete) needs a comment with the reason, and the `wontfix`/`duplicate` label.
