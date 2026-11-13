---
name: release
description: Prepare and verify a Booking API release - check readiness of develop, draft release notes from merged PRs and closed issues, confirm the VERSION bump, and prepare the develop -> master PR plus the deployment checklist (low-load window, smoke test, secondary realignment). Use for "prepare a release", "what is going out", "release notes", "is develop ready for master", "cut v1.2.0". It never merges or deploys by itself.
---

# Release (develop → master → primary)

Releases follow `CLAUDE.md` GitFlow: feature/fix PRs land in `develop` (verified on the secondary), then **one PR `develop` → `master`**, then the owner deploys the primary in a low-load window. Milestone = release (`vX.Y.Z`, matches `VERSION` in `globals.py`).

## 1. Check readiness (read-only)

```bash
python .claude/skills/release/scripts/release_check.py            # compares origin/develop with origin/master
python .claude/skills/release/scripts/release_check.py --notes     # also prints release notes (Markdown) for the PR body
```

It reports: version on `develop` vs `master` (must be higher, SemVer), merged PRs and the issues they close, latest CI runs on `develop`, open `P0`/`P1` bugs and open issues of the milestone, and whether `master` has commits missing in `develop` (a hotfix not merged back: fix that first).

Stop and tell the user if: CI on `develop` is red, the version was not bumped, there are open `P0` bugs, `master` is ahead of `develop`, or the secondary is not running `develop` yet / was not verified (ask the owner; you cannot see it).

## 2. Draft the release PR

Only after the user agrees. Branch protection requires a PR and the `tests` check on `master`.

```bash
gh pr create --base master --head develop --title "release: vX.Y.Z" --body-file notes.md
```

Body = the `--notes` output plus: deployment impact aggregated from the PRs (restarts: web/worker/beat; migrations; image rebuild; new env variables), `Closes` is **not** needed (issues are already closed by the `close-linked-issues` workflow), and the milestone link.

## 3. Deployment checklist (the owner executes; production runbook is in the `booking-api-ops` agent)
- [ ] Low-load window, outside the salon's opening hours.
- [ ] Merge the PR (owner), `git pull` on the primary as `ubuntu`, rebuild images only if `Dockerfile.*`/`requirements.txt` changed, restart what changed.
- [ ] `scripts/smoke_test.sh --url <api> --expect-version X.Y.Z --worker <container>` passes.
- [ ] Watch `/health` and the worker log for a few minutes.
- [ ] Re-deploy the secondary (it runs `develop`, which now equals `master`).
- [ ] Close the milestone and move leftover issues to the next one: `gh api -X PATCH repos/daniieelgs/booking_api/milestones/<n> -f state=closed`.
- [ ] Optionally tag: `git tag -a vX.Y.Z origin/master -m "vX.Y.Z"` and a GitHub release from the notes (ask first; tags are public).

## Hotfix releases
Urgent fixes use `hotfix/*` from `master` (see the `scrum-master` agent); bump the patch version in the hotfix PR, then open `master` → `develop`.
