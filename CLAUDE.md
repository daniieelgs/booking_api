# CLAUDE.md

Guidance for Claude Code (claude.ai/code) in this repo. Keep this file short: project context, conventions and pointers. Procedures belong in the agents and skills below; deep dives in `docs/`; pending work in the GitHub backlog (Issues + Project), never here.

## Project

Multi-tenant booking backend ("locals" = businesses). One customer today: **SUBLIME HAIR SALON** (public site https://www.sublimebarberia.com/, staff backoffice https://backend.sublimebarberia.com/, both separate frontends that only consume this API). Stack: Flask (flask-smorest), Celery, Redis, MariaDB, Docker. Full endpoint list in `/openapi.json` (Swagger UI only with `FLASK_DEBUG=1`).

## Map: agents, skills, docs, backlog

| Need | Use |
|---|---|
| Production errors, logs, emails not arriving, deploy, new features/bug fixes in the app | agent **`booking-api-ops`** (holds the production runbook) |
| Write/run tests, hunt bugs, re-verify fixes | agent **`test-engineer`** + skills **`write-tests`**, **`test-bug-report`** |
| Backlog, branches, PRs, repo hygiene and settings, hotfix PRs | agent **`scrum-master`** + skill **`backlog`** |
| Release `develop` → `master`: readiness, notes, deploy checklist | skill **`release`** |
| Add or change an endpoint/resource | skill **`new-endpoint`** |
| Security review of a diff/PR/area (read-only) | agent **`security-reviewer`** |
| Keep docs true to the code, document features, keep this file short | agent **`docs-keeper`** + skill **`docs-check`** |
| Pending work (bugs, features, tasks, roadmap) | GitHub Issues + Project board of `daniieelgs/booking_api` (see `backlog` skill) |
| Infrastructure, servers, deployment | `docs/infrastructure.md` |
| Email delivery guarantees, templates, SMTP providers | `docs/email-system.md` |
| Test layout, commands, CI, Python env | `docs/testing.md` |
| Database backups and restore | `docs/db-backups.md` |
| Past incidents | `docs/lessons-learned.md` |

Private server access (SSH, paths, account limits) is in `.claude/servers.local.md` (gitignored; template `servers.example.md`).

## Language convention

- **En español**: todas las explicaciones y la documentación: cuerpo de los commits, descripción de las PR y de las issues, `docs/`, `CLAUDE.md`, `changelog.md`, descripciones de Swagger (docstrings de los endpoints), comentarios del código y respuestas al usuario.
- **En inglés**: los nombres: ramas, asunto del commit (`fix: ...` en Conventional Commits), título de PR e issue, rutas y campos de los endpoints, identificadores del código, nombres de tests y los títulos de sección de las plantillas de issue (los scripts los leen). Los textos `message` de los `abort(...)` se mantienen como están para no romper a los frontends.
- Los ficheros ya escritos en inglés se traducen cuando se toquen (agente `docs-keeper`), sin PR masivas solo de traducción salvo que se pida.

## Commands

All from the repo root (`booking_api/`): file paths are built from `os.getcwd()`, running elsewhere breaks image/log/report storage.

- Setup: `.env` in the root (see `.env.example`), plus `docker/.env` and `db/.env` for Docker. `pip install -r requirements.txt` (Python 3.11; the file is **UTF-16**, never re-save it as UTF-8).
- Run: `flask run` or `python app.py` (both use `create_app()` from `app.py`).
- Migrations (Flask-Migrate; `migrations/` is gitignored, run `flask db init` once per environment): `flask db migrate -m "..."` then `flask db upgrade`.
- Celery: `celery -A make_celery.celery worker --loglevel=info -Q priority,default` and `celery -A make_celery.celery beat --loglevel=info`.
- Admin token: `python access.py --generate <days> --name <name>` (`--help` for more).
- Docker: build `./build.sh` or `./build.ps1`; dev `docker-compose --env-file ./docker/.env -f ./docker/docker-compose.yml up`; prod `docker compose --env-file ./docker/.env -f ./docker/docker-compose.prod.yml up -d` (details and the secondary's different env file in `docs/infrastructure.md`).
- Tests: `python -m pytest tests/` (no Docker). Tiers, services tier, redelivery, CI and Python env in `docs/testing.md`. Don't run two pytest processes at once.

## Architecture

- **App factory, no package layout.** `app.py`'s `create_app(config)` registers blueprints and wires JWT/Celery/CORS/logging; `wsgi.py` and `make_celery.py` import the `app` built at module level there (skipped when `TEST_PERFORMANCE` is set: a separate load-test mode, not the normal suite).
- **Config layering.** `config.py` (`Config`) ← `default_config.py` (from `globals.py`) ← `tests/config_test.py` / `tests/config_test_performance.py`. `create_app()` takes a config instance so tests swap it.
- **`globals.py` is the single source of environment config** (`DEFAULT_X = ...` then `X = os.getenv('X', DEFAULT_X)`), the global logger and the `log(...)` function (structured, per-uuid cache). Add new env-driven constants there. If a value must be overridable at runtime (tests), read it with `os.getenv()` inside a getter instead of binding at import (see `helpers/path.py`, `helpers/ReportController.py`).
- **Versions.** `API_VERSION` (`'v1'`) is the URL/OpenAPI tag; `VERSION` in `globals.py` is the release version returned by `GET /version`. Don't conflate them.
- **Resources = flask-smorest blueprints, one file per domain** in `resources/`, registered with a prefix from `getApiPrefix()` (`api/v1`). Exceptions: `public_files.py` (`/public`) and `status.py` (`/health`, `/version`) at the root. Pattern: `MethodView` + `@blp.route`, `@blp.arguments(Schema)`, stacked `@blp.response(code, description=...)` for errors plus one 2xx with the schema, docstring = Swagger description. All schemas in `schema.py`.
- **Auth, three mechanisms mixed per endpoint:** (1) `@jwt_required(refresh=True|fresh=True)`, identity = local id; (2) hand-rolled admin token check (`helpers/security.py` `check_admin_token()`/`check_admin_request()`, `resources/admin.py`) against `SessionTokenModel` + `ADMIN_ROLE`; (3) no decorator = public (`public_files.py`, `status.py`, public GETs in `work_group.py`/`service.py`, `report.py`'s fallback endpoint, which intentionally accepts arbitrary JSON). Session tokens are revocable (`SessionTokenModel` is the JWT blocklist, `token_in_blocklist_loader` in `app.py`).
- **Status codes:** `401` missing/invalid/expired credentials; `403` authenticated but not allowed (another local's data, worker doing a local-only action); `404` resource does not exist for that local.
- **`@log_route`** (`helpers/LoggingMiddleware.py`) wraps most handlers: injects `_uuid`, logs request/response, turns uncaught exceptions into JSON 500 (and re-raises). Handlers accept `_uuid=None` last.
- **DB access through `db.py` helpers** (`addAndCommit`, `deleteAndCommit`, `addAndFlush`, `deleteAndFlush`, `commit`, `rollback`), never raw `db.session`; they stamp `datetime_created/updated`.
- **Domain errors** in `helpers/error/<Domain>Error/`, one class per file; handlers `abort(code, message=str(e) if DEBUG else '<generic>')`, never leak internals when `DEBUG` is off.
- **File storage is local disk under `os.getcwd()`**: `helpers/path.py` (`PUBLIC_FOLDER`, re-read per call) and `helpers/ReportController.py` (thread lock + OS file lock, multi-process safe).
- **Celery:** `celery_app/celery_config.py` `make_celery()`, tasks in `celery_app/tasks.py`, beat schedule inline in `create_app()`.
- **Timezone:** every naive `datetime` in the DB is wall-clock time in the local's own timezone (`LocalModel.location`): localize with `naiveToAware(value, local.location)`, compare against `now(local.location)`. Absolute instants (JWT `exp`) use UTC explicitly. See `helpers/DatetimeHelper.py`.

## Business rules

- **Customer flow (no registration):** pick a service, optionally a worker (else the backend assigns one), a free slot, fill name/email/phone. Optional confirmation email only if `local_settings.booking_timeout` (minutes) is set, otherwise auto-cancel via `check_booking_status`; `NULL`/`-1` disables it (**disabled for Sublime**: bookings go straight to confirmed). Then a "confirmed" email with a user-token link (valid until the booking ends) to cancel (update exists but is **disabled for Sublime**); cancel/update send their own email.
- **Backoffice:** only a local's workers log in (`/api/v1/local/login`): booking history/upcoming, cancel bookings, manage services, timetable, closed dates, workers and their services.
- **Auth levels / roles:** public, local/worker (JWT), user (email token, own booking only), admin. Roles `A` admin, `L` local, `U` user. Booking status `P` pending, `C` confirmed, `D` done, `X` cancelled.
- **A worker can never have two overlapping bookings.** Layer 1: short-lived Redis lock per local (`waitAndRegisterBooking`/`perform_atomic_booking` in `helpers/BookingController.py`, `WATCH` + `SETEX`, key = `local_id`, expiry `MAX_TIMEOUT_WAIT_BOOKING`). Layer 2: the DB is the source of truth (`getBookings(...)` checks `C`/`P` overlaps before inserting). The secondary has its own Redis, so only layer 2 spans both servers.
- **Every booking must end up with its email**, even across SMTP outages or restarts: keep the queue durable (Redis AOF, `noeviction`) and never drop tasks silently. Details in `docs/email-system.md`.
- **Data model** (one table per concept): `booking`, `closed`, `file`, `local`, `local_settings`, `service`, `session_token`, `smtp_settings`, `timetable`, `worker`, `work_group` (a local can have several, each with services and workers); join tables `service_booking`, `work_group_worker`; lookups `status`, `weekday`.

## Infrastructure (summary)

Two servers, same codebase, both on the **same MariaDB (on the primary)**. Primary = `master`, main API + DB + backup container; secondary = `develop`, fallback API with its own Redis/Celery. Code is bind-mounted, so a `git pull` needs a container restart. `GET /health` → `ok`/`degraded`/`error`/`critical`. DB backups: nightly dump + binlog PITR + encrypted copy to the secondary (`dbbackup/`, `docs/db-backups.md`). Everything else: `docs/infrastructure.md`; operations: `booking-api-ops`.

## Security rules

- Never commit or paste secrets: `.env*`, tokens, SMTP/DB/Redis passwords, DB dumps, anything under `private/` or `public/`. The repository is **public**: issues, PRs, commits and docs must not contain secrets, customer data, raw production logs or server addresses.
- Never expose internal error details when `DEBUG` is off; keep the `401`/`403`/`404` semantics above; check ownership (`local_id`) on every local-scoped resource.
- No production access from unattended/cloud sessions (no `servers.local.md`, no `booking-db` credentials): don't ask for or invent credentials. Production, SSH and deployments are done by the owner or in a session he supervises.
- Agents never merge a PR, push to `master`/`develop`, deploy, change repo settings or run destructive DB/Redis commands without the user's explicit confirmation.
- Deploying `master` affects the salon's customers: only in low-load hours, outside opening hours; verify with `scripts/smoke_test.sh` afterwards.

## Git workflow (GitFlow, mandatory for humans and agents, local or cloud)

`master` = production (primary), `develop` = integration (secondary). Never commit directly to either; they change only through a **pull request**.

- Branches off `develop`: `feature/<name>`, `fix/<name>`; `hotfix/<name>` off `master` (PR into `master`, then merge `master` back into `develop`; the branch rulesets let the repo admin bypass them only via a PR, with the owner's explicit approval; the `scrum-master` agent prepares it). Start with `git fetch origin && git switch -c <type>/<name> origin/develop`; if the environment pre-created another branch, switch to a correct one before committing. `claude/` prefix only if the environment refuses anything else (`claude/feature-<name>`, say so in the PR).
- **One issue/bug = one branch = one PR** with its own commits; never mix a fix with a feature or refactor. Related set of tasks: umbrella branch off `develop`, one sub-branch per task merged into it, one PR umbrella → `develop`. Tests-only or docs-only changes also get their own branch.
- **Every PR links its issue** (`Closes #n` in the body; the workflow `close-linked-issues` closes it when the PR merges into `develop`) and follows `.github/pull_request_template.md`: what/why, real test output, deployment impact. Open the PR into `develop` (never `master`).
- Small atomic Conventional Commits (`fix:`, `feat:`, `test:`, `docs:`, `chore:`, `refactor:`), asunto en inglés e imperativo, cuerpo en español que explica el porqué; a fix includes its regression test. No history rewriting on pushed/shared branches.
- **Bump `VERSION` in `globals.py`** (SemVer: fix → patch, feature → minor, breaking → major) when behaviour or the API changes; docs/test-only PRs don't. Once per umbrella PR.
- Run `python -m pytest tests/` before opening the PR (and the services tier when touching DB/Redis/Celery/bookings/email, if Docker is available); paste the results in the PR.
- Promotion: feature/fix → PR into `develop` → verified on the secondary → PR `develop` → `master` (full CI) → deploy to the primary in low-load hours.
- If a test fails for an unclear reason or a requirement is ambiguous, stop and report; never mark a failing test as expected-failure. Bugs found while doing something else go to the backlog (skill `backlog`) instead of being fixed inline.
- Procedures (opening branches/PRs, releases, branch cleanup, repo settings) are carried out by the `scrum-master` agent.

## Cloud sessions

Same rules, no lighter flow. Cloud ships Python 3.13 but the pinned requirements need 3.11: use `.venv/bin/python -m pytest ...` (a `SessionStart` hook in `.claude/settings.json` creates it; see `docs/testing.md`). Findings must survive the session: `private/` is gitignored and absent in cloud, so put bugs in the backlog (issues) and the PR description.

## Agents and skills

- Agents (`.claude/agents/`): `booking-api-ops` (app + production), `test-engineer` (QA), `scrum-master` (GitHub backlog/branches/PRs/hotfixes), `security-reviewer` (read-only security review), `docs-keeper` (documentation).
- Skills (`.claude/skills/`): `backlog` (GitHub Issues/labels/board; scripts `issue.py`, `setup_repo.py`), `write-tests` (test conventions per tier, `check_tests.py` guard), `test-bug-report` (run all tiers, analyse failures into `private/reports/tests/*.json` + HTML, publish/link bugs to the backlog), `new-endpoint` (conventions checklist + template), `release` (`release_check.py`: readiness and notes), `docs-check` (`check_docs.py`: broken refs, size budget).
- When a task has an agent or skill that knows how, don't re-describe the procedure here: put it in the agent/skill.
