# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands assume the working directory is the repo root (`booking_api/`) — file paths throughout the app are built from `os.getcwd()`, so running from anywhere else breaks image/log/report storage.

**Setup**
- Create `.env` in the repo root (see `.env.example` for the full list of variables), plus `docker/.env` and `db/.env` if running via Docker.
- `pip install -r requirements.txt` — note: `requirements.txt` is UTF-16 encoded; editing it with a plain-text writer that assumes UTF-8 will corrupt it.

**Run the app**
- Dev server: `flask run` (Flask auto-detects `app.py`) or `python app.py` — both build the Flask app via `create_app()` in `app.py`.
- Swagger UI is only mounted when `FLASK_DEBUG=1` (see `OPENAPI_URL_PREFIX`/`OPENAPI_SWAGGER_UI_PATH` in `app.py`).
- DB migrations (Flask-Migrate, `migrations/` is gitignored — run `flask db init` once per environment before the first migration): `flask db migrate -m "..."` then `flask db upgrade`.
- Celery worker: `celery -A make_celery.celery worker --loglevel=info -Q priority,default`
- Celery beat: `celery -A make_celery.celery beat --loglevel=info`
- Admin token CLI: `python access.py --generate <days> --name <name>` (see `python access.py --help` / `access.py`'s `showHelp()` for `--list`, `--remove`, `--remove-all`, `--env`, `--data`).

**Docker**
- Build images: `./build.sh` or `./build.ps1` (builds `booking-base` from `docker/Dockerfile.base`, then `booking-flask` from `docker/Dockerfile.flask`).
- Run dev stack: `docker-compose --env-file ./docker/.env -f ./docker/docker-compose.yml up`
- Run prod stack: `docker compose --env-file ./docker/.env -f ./docker/docker-compose.prod.yml up -d` (HTTPS via Apache + mod_wsgi, see `docker/docker-entrypoint.sh` and `apache-flask.conf.template`). The primary server only has Compose v2 (`docker compose`, not `docker-compose`). The Compose project name is `docker` (derived from the `docker/` folder), hence the container names `docker-web-1`, `docker-worker-1`, etc.

**Tests**
- Layout: `tests/unit/` (no Flask app over HTTP; pure logic with mocks, `fakeredis` for the real WATCH semantics of the booking lock, and `tests/unit/db_support.py` `DbTestCase` = bare Flask + in-memory SQLite + JWT for helpers that need `db.session`), `tests/integration/` (full Flask app over HTTP with SQLite, `flask_testing.TestCase`; no real DB/Redis), `tests/integration/services/` (marker `services`: real MariaDB 10.5.19 + Redis 7.2.4 + a Celery worker from `docker/docker-compose.test.yml`), `tests/backup/` (the `dbbackup/` suite, stdlib only, plus `tests/backup/e2e/run_e2e.sh`). Shared helpers stay in `tests/` (`config_test.py`, `configure_local_base.py`). `pytest.ini` deselects `services` by default.
- The root `conftest.py` sets `FLASK_DEBUG=1` before `globals` is imported: `REDIS_TEST_MODE`/`EMAIL_TEST_MODE` are only honoured when `DEBUG` is on, so the suite must not depend on a developer's `.env`.
- Run all (no Docker): `python -m pytest tests/`
- Run one file: `python -m pytest tests/integration/test_work_group.py -v`
- Run one test: `python -m pytest tests/integration/test_work_group.py::TestWorkGroup::test_method -v`
- Real-services tier: `docker compose -f docker/docker-compose.test.yml up -d --wait`, then `RUN_INTEGRATION_TESTS=1 python -m pytest tests/integration/services -m services -v` (run that directory on its own, `globals.py` binds env at import), then `docker compose -f docker/docker-compose.test.yml down -v`. See `tests/integration/services/README.md`.
- Post-deploy check: `scripts/smoke_test.sh --url <api> [--expect-version X] [--worker <container>]` (exit 1 if `/health`, `/version` or the Celery worker is wrong).
- CI: `.github/workflows/tests.yml` (CI, not CD). On push/PR to `develop` only the unit tests run; on `master` (push, or PR targeting it) also the SQLite integration + backup tests and the job `services` (real MariaDB/Redis/Celery in Docker).
- Test agent: `.claude/agents/test-engineer.md` (QA specialist that uses the two skills below: writes tests, runs the suite, analyses failures and hunts bugs; it never edits application code nor marks failing tests as expected failures; bug fixing stays with `booking-api-ops` or the user).
- New-tests skill: `.claude/skills/write-tests/` (conventions per tier with templates, and `scripts/check_tests.py`, a guard that fails on `xfail`/`expectedFailure`: failing tests must stay red, never be marked as expected failures).
- Test report skill: `.claude/skills/test-bug-report/` runs every tier, analyses each failure in depth and writes `private/reports/tests/{results.json,findings.json,report.html}` (gitignored); after fixing bugs it re-runs only the affected tests (`recheck.py`) and updates the JSON. An agent fixing bugs should read `findings.json` (`findings.py list/show`) instead of re-running the suite.
- Don't run two pytest processes at once: the SQLite test DB (`instance/data_test.db`) is shared and they collide.
- A separate "performance test" mode exists (`TEST_PERFORMANCE=1` env var), which changes `app.py`'s startup path and API prefix — see `tests/config_test_performance.py` and `resources/unavaliable_api.py`. Don't confuse it with the normal test suite.

## Architecture

**App factory, no package layout.** Everything hangs directly off the repo root (no top-level `__init__.py`). `app.py`'s `create_app(config)` builds the Flask app, registers all blueprints, and wires JWT/Celery/CORS/logging; `wsgi.py` and `make_celery.py` both import the already-built `app` object from `app.py` (module-level `app = create_app()` runs at import time unless `TEST_PERFORMANCE` is set).

**Config layering.** `config.py` (`Config`, plain data holder) ← `default_config.py` (`DefaultConfig`, populates `Config` from `globals.py`) ← `tests/config_test.py` (`ConfigTest`, points at SQLite, seeds `UserSessionModel`/`StatusModel`/`WeekdayModel`, mints an `ADMIN_TOKEN`) / `tests/config_test_performance.py` (`ConfigTestPerformance`, similar but for load-testing). `create_app()` takes a `Config` instance so tests can swap in `ConfigTest` without touching `app.py`.

**`globals.py` is the single source of truth for environment config.** Every setting follows `DEFAULT_X = ...` then `X = os.getenv('X', DEFAULT_X)`. It also owns the global logger (`setLogger`/`getLogger`), the app singleton (`setApp`/`getApp`), and the `log(message, level, uuid, request, response, error, save_cache)` function used everywhere for structured logging (keeps a per-uuid cache and flushes it on a background thread when `save_cache=True`). Add new env-driven constants here, following the existing pattern — unless the value needs to be overridable at runtime (e.g. in tests), in which case read it via `os.getenv()` inside a getter function instead of binding it as a module-level constant at import time (see `getReportsFile()`/`getMaxReportSize()` in `helpers/ReportController.py` vs. the plain `PUBLIC_FOLDER` handled the same way in `helpers/path.py`).

**Timezone convention.** Every naive `datetime` in the database means wall-clock time in the local's own timezone (`LocalModel.location`); localize it with `naiveToAware(value, local.location)` and compare against `now(local.location)`. Absolute instants (JWT `exp`) use UTC explicitly, never the server's timezone. See the comment in `helpers/DatetimeHelper.py`.

**Two separate "version" concepts** — don't conflate them: `API_VERSION` in `globals.py` (default `'v1'`) is the URL/OpenAPI version tag; `VERSION` in `globals.py` (default `'1.0.0'`) is the application release version returned by `GET /version`.

**Resources = flask-smorest blueprints, one file per domain**, registered in `app.py` with a URL prefix built from `API_PREFIX` (`api/v1`) via `getApiPrefix()`. Exceptions: `public_files.py` mounts at `/{PUBLIC_FOLDER_URL}` (default `/public`) and `status.py` mounts at the domain root (`/health`, `/version`) so health checks don't need to know the API version. Endpoint pattern: `MethodView` classes decorated with `@blp.route(...)`, `@blp.arguments(Schema)` for body/query validation, a stack of `@blp.response(code, description=...)` for documented error responses plus one `@blp.response(2xx, Schema)` for the success payload, and the method's docstring as the Swagger description. All Marshmallow schemas live in one monolithic `schema.py`.

**Auth is three separate mechanisms, mixed per-endpoint:**
1. `@jwt_required(refresh=True)` / `@jwt_required(fresh=True)` (flask-jwt-extended) — identity is the local's id (`get_jwt_identity()`); most local-scoped CRUD uses this.
2. Hand-rolled admin token check — `helpers/security.py`'s `check_admin_token()`/`check_admin_request()` (or the inlined equivalent in `resources/admin.py`), which decodes the JWT manually and checks it against `SessionTokenModel` + `ADMIN_ROLE`.
3. No decorator at all → public endpoint (e.g. `public_files.py`, `status.py`, the public GET-by-id routes in `work_group.py`/`service.py`, and `report.py`'s fallback endpoint, which intentionally has no auth and accepts arbitrary JSON).

Session tokens are revocable: `SessionTokenModel` backs a JWT blocklist checked in `app.py`'s `token_in_blocklist_loader`.

**`@log_route` (`helpers/LoggingMiddleware.py`)** wraps most resource handlers: it generates a request UUID, injects it as an `_uuid` kwarg into the handler, logs the request/response via `globals.log()`, and converts any uncaught exception into a JSON 500 (re-raising afterward so Flask's normal error handling still applies). Handlers under it accept `_uuid=None` as their last parameter.

**DB access goes through `db.py`'s helpers**, not raw `db.session` calls: `addAndCommit`/`deleteAndCommit`/`addAndFlush`/`deleteAndFlush`/`commit`/`rollback`. `addAndCommit`/`addAndFlush` auto-stamp `datetime_created`/`datetime_updated` via `addDateTimes()`.

**File storage is local disk, rooted at `os.getcwd()`.** `helpers/path.py` builds public asset paths (`{PUBLIC_FOLDER}/{local_id}/images/...`) from the `PUBLIC_FOLDER` env var, re-read on every call (not cached at import) so tests can redirect it (see `tests/config_test.py` setting `PUBLIC_FOLDER=tests/public`). `helpers/ReportController.py` follows the same re-read-per-call convention for `REPORTS_FILE`/`MAX_REPORT_SIZE`/`MAX_REPORTS_FILE_SIZE`, and additionally serializes writes with both a `threading.Lock` (in-process) and an OS-level file lock (`fcntl`/`msvcrt`, cross-process) since the app can run multi-process under Apache/mod_wsgi.

**Celery**: `celery_app/celery_config.py`'s `make_celery()` binds a `Celery` instance to the Flask app context; task definitions live in `celery_app/tasks.py`; the beat schedule is configured inline inside `create_app()` in `app.py` (`app.config.from_mapping(CELERY=dict(..., beat_schedule={...}))`).

**Domain errors live under `helpers/error/<Domain>Error/`** (one exception class per file, e.g. `helpers/error/BookingError/AlredyBookingException.py`). Resource handlers catch these and translate them via `abort(code, message=str(e) if DEBUG else '<generic message>')` — never leak internal error details when `DEBUG` is off.

**Tests** (`tests/`) use `flask_testing.TestCase`. The shared fixture pattern: `create_app()` returns `create_app(config_test)`; `setUp()` calls `db.create_all()` then `config_test.config(db=db)`; `tearDown()` calls `db.session.remove()`, `db.drop_all()`, `config_test.drop(self.locals)`. `tests/config_test.py` also exposes `getUrl(*parts)` (prefixes with `api/v1/`) and `setParams(url, **params)` for building request URLs in tests.

## Product context

Multi-tenant booking backend ("locals" = businesses). Today there is a single customer, **SUBLIME HAIR SALON** (local id `151b1bf60f3e4026814183ffe9c75148`), with a public website (https://www.sublimebarberia.com/) and a staff backoffice (https://backend.sublimebarberia.com/). Both are separate frontends that only consume this API. The full endpoint list is in `/openapi.json` (Swagger UI only with `FLASK_DEBUG=1`).

**Customer flow (no registration).** The site lists services, prices, durations, opening hours and contact/social info; the customer picks a service, optionally a worker (otherwise the backend assigns one), a free slot, and fills name/email/phone. Then:
1. Optional confirmation email: only if `local_settings.booking_timeout` is set (minutes); if the customer does not confirm in time the booking is auto-cancelled (`check_booking_status`). `NULL`/`-1` disables it — **disabled for Sublime**, so bookings go straight to confirmed.
2. "Booking confirmed" email with the booking data and a link containing a user token (valid until the booking ends) to cancel — and update, but **update is disabled for Sublime** (no frontend yet).
3. Cancelling/updating sends another email (cancelled / updated).

**Backoffice flow.** Only a local's workers authenticate (`/api/v1/local/login`). They see booking history and upcoming bookings with status, cancel bookings, and manage services, timetable, closed dates (holidays), workers and which services each worker offers.

**Auth levels.** Public (services, timetable, free slots, public files), local/worker (JWT, private booking data), user (token from the email, own booking only), admin (hand-rolled admin token). Roles: `A` admin, `L` local, `U` user. Booking status codes: `P` pending, `C` confirmed, `D` done, `X` cancelled.

## Data model (one table per concept)

`booking` (all bookings of all locals: start/end, client name/phone/email/comment, status, worker, services, `email_confirmed`/`email_cancelled`/`email_updated` flags, `uuid_log`, `server_name` = which server created it), `closed` (closing dates), `file` (public files per local: email templates, logos, gallery), `local` (business data + password hash), `local_settings` (public settings: domain, socials, contact, confirm/cancel/update link templates containing the user-token placeholder, `booking_timeout`), `service` (price, duration), `session_token` (user and worker tokens; also the JWT blocklist), `smtp_settings` (per-local SMTP providers), `timetable`, `worker`, `work_group` (a local can have several groups, e.g. nails vs hair, each with its own services and workers). Join tables: `service_booking`, `work_group_worker`; lookup tables: `status`, `weekday`.

## Booking concurrency and Redis

A worker can never have two overlapping bookings. Two layers: (1) `waitAndRegisterBooking`/`perform_atomic_booking` in `helpers/BookingController.py` take a short-lived Redis lock per local (`WATCH` + `SETEX`, key = `local_id`, expiry `MAX_TIMEOUT_WAIT_BOOKING`) so two concurrent requests cannot take the same slot; (2) the DB is the source of truth — `getBookings(...)` checks overlaps for `C`/`P` bookings before inserting. Redis connection helpers live in `helpers/Database.py` (pooled, retry with backoff, password from `REDIS_PASSWORD`). Redis is also the Celery broker/result backend, so **Redis must not lose or evict data**: it runs with AOF + `--maxmemory-policy noeviction`, a password, and a named volume (`redis-data`). `GET /health` returns only `{"status": ...}` (always HTTP 200): `ok` (database, Redis and a Celery worker answering), `degraded` (worker down: bookings work, emails delayed), `error` (Redis down: no bookings) or `critical` (database down); worst failure wins, see `helpers/HealthController.py` (worker ping cached `HEALTH_CACHE_SECONDS`=10 s, timeout `HEALTH_WORKER_TIMEOUT`=1 s). Note: the secondary server has its **own** Redis, so the lock does not span both servers — only the DB overlap check does.

## Database backups

Implemented on branch `feature/db-backups` (see `docs/db-backups.md` for the runbook; **not deployed yet** until merged `develop` → `master` and rolled out). Standalone stdlib-only package `dbbackup/` run by its own container `backup` (`docker/Dockerfile.backup`, image `booking-backup`, code bind-mounted read-only like the other services). It deliberately imports nothing from the Flask app and uses a dedicated read-only DB user (`scripts/create-backup-db-user.sh`), never root.

- **Binlog PITR**: the prod `database` service runs with `--log-bin=mysql-bin --binlog-format=ROW --expire-logs-days=7` (explicit basename: the default derives from the container hostname). Enabling it needs one DB restart.
- **Service loop** (`dbbackup/service.py`, one tick every 30 s, state persisted in `/backups/state/state.json`): nightly `mysqldump --single-transaction --master-data=2` at 04:00 (catches up if the container was down), `FLUSH BINARY LOGS` + archive of *closed* binlogs every 6 h and right after the dump, encrypted (`age`, public recipient only) delivery to the secondary via `rsync` over SSH with retries every 15 min (undelivered files are never pruned), local retention (2 dumps, 7 days of binlogs), heartbeat to Uptime Kuma (push monitor). Local dumps stay unencrypted (same exposure as the live data, restore needs no key); only what leaves the primary is encrypted.
- **Secondary** only receives: restricted Linux account `dbbackup` with `restrict,command="rrsync -wo ..."`; retention (`dbbackup/prune.py`, last 3 dumps + needed binlogs) runs from the secondary's own cron so a compromised primary cannot delete shipped copies. Don't confuse this account with the DB user `backup`.
- **`scripts/restore.sh`** recovers deleted rows without touching live data: newest dump before `--until` → throw-away MariaDB (compose profile `restore`, service `restore-db`) → replay binlogs → compare primary keys with the live DB → `INSERT IGNORE` SQL (dry run by default, `--apply` to insert, `--inspect` to find the incident time). **`scripts/promote-secondary.sh`** starts `booking-db-promoted` on the secondary from the latest dump + contiguous binlogs, decrypting through pipes (no plaintext on disk) and printing the manual steps to repoint the app; it never changes the secondary's existing containers or `.env`.
- Tests: `python -m pytest tests/backup -q` (unit, no Docker/DB, imports nothing from the Flask app; keep `tests/__init__.py` empty so it stays that way) and `bash tests/backup/e2e/run_e2e.sh` (full integration with real MariaDB/rsync/SSH/age in Docker; run it before merging changes to `dbbackup/`, `scripts/` or the compose file). `.gitattributes` forces LF on `*.sh`: CRLF breaks them on Linux.
- The old `daily_worker` → `helpers/Backup.py` dump at 03:00 still exists and is redundant; remove it once the new system is verified in production.

## Email system

- Sent by Celery task `send_mail_task` (queue `priority`, `max_retries=MAX_RETRIES_SEND_EMAIL`=12, retry delay `60 * RETRY_SEND_EMAIL` seconds = 2 h by default, i.e. 24 h of margin) in `celery_app/tasks.py`; rendering/sending in `helpers/EmailController.py`. `check_booking_status` and `daily_worker` (backup at `DAILY_HOUR:DAILY_MINUTE`, default 03:00) run on queue `default`; beat schedules only `daily_worker`.
- Templates are per-local HTML files stored as public files: `public/<local_id>/pages/email_{confirmation,confirmed,cancelled,updated}.html`, uploaded through `POST /api/v1/files/pages` (served at `/public/pages/local/<local_id>/<name>`). The `<title>` is the email subject; `KEYWORDS_PAGES` placeholders in `globals.py` are substituted in `render_page`. **`public/` is gitignored** — templates exist only on each server's disk.
- Providers: `local.local_settings.smtp_settings` rows, tried in `priority` order by `mail_local_sender`. Each row has daily/monthly caps, counters and reset dates; when a provider hits its free-tier cap or fails, the next one is used. Sublime has three (Brevo `smtp-relay.brevo.com`, SendGrid `smtp.sendgrid.net`, `smtp.servidor-correo.net`) so the combined free tiers cover the month. Passwords are stored encrypted (`helpers/security.py` `decrypt_str`, key `CRYPTO_KEY`).
- Hard requirement: every booking must end up with its email, even across SMTP outages or restarts. Keep the queue durable (Redis AOF) and never drop tasks silently.

## Infrastructure and deployment

Two servers, same codebase, both read/write the **same MariaDB (on the primary)**:

| | Primary `booking-api.es` | Secondary `booking-api.ddns.net` |
|---|---|---|
| Role | Main API + the database | Fallback when the primary is down or a booking returns 500; the frontend then posts a report to `POST /api/v1/report/fallback` |
| Stack | Docker Compose prod: `web` (`booking-flask`, Apache + mod_wsgi, terminates SSL), `database` (`mariadb:10.5.19`), `worker` + `beat` (`booking-base`, Celery), `redis` (`redis:7.2.4-bookworm`), `autoheal` | Docker; `flask run --port 5001` (Werkzeug), own Celery worker/beat and own Redis, DB = primary's published port 3307 |
| Project path | `/home/ubuntu/booking_api` (bind-mounted as `/app` in every container) | `/home/daniieelgs/booking/backend/booking_api` |
| Git branch deployed | `master` | `develop` (as of 2026-11-02 it is ~10 commits behind `master`; check before assuming parity) |
| Access | see `.claude/servers.local.md` (private, gitignored) | same |

- **Secondary deployment (verified 2026-11-06).** Docker there is the snap package (socket `/var/run/docker.sock` is `root:docker`; the snap assigns that group each time `dockerd` starts because group `docker` exists, so no manual `chgrp` should be needed; if it ever shows `root root`, run `sudo snap disable docker && sudo snap enable docker` (restarts every container on that host); `daniieelgs` is in group `docker`). The stack must be started with the secondary's own env file, **not** `docker/.env` (that one is the prod config: Apache/SSL, port 442, and crash-loops the web container): `cd /home/daniieelgs/booking/backend/booking_api && docker compose --env-file ./docker/.env2 -f ./docker/docker-compose.yml up -d` (`PORT=5001`, `FLASK_ENV=development`, `REDIS_PORT=6378`, plus `REDIS_PASSWORD`, which must also be in `.env` and inside `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND`). Public traffic reaches it through 443 (a front proxy), port 5001 is not reachable from outside. Other unrelated projects share that Docker daemon (jarvis, mylove/fastapi_*, gotify, uptime-kuma): only touch containers named `docker-*`; never restart the snap or other compose projects.

- **Restricted Docker access for Isma (secondary).** Isma (`isma`, project developer) has no `docker` group and no general sudo. He runs `sudo booking-docker <action>`, a root-owned wrapper (`/usr/local/bin/booking-docker`, allowed by `/etc/sudoers.d/booking-docker`) that only accepts `ps` (lists just the `docker-*` containers of this project), `logs <container> [1-2000 lines]` (real logs, not redacted) and `restart <container>` (only `docker-web-1`, `docker-worker-1`, `docker-beat-1`); anything else (`exec`, `run`, other projects' containers, restarting redis/database) is rejected. Container names are a hard-coded allow-list and arguments are validated, never passed through. **These two files live only on the secondary and are intentionally not in the repo**; if the container names or the project path change, edit the wrapper there with `sudo`. Tested 2026-11-06 (allowed actions work, `docker ps`/other containers/`exec` are denied).

**Branch per server (by design):** the primary always runs `master`; the secondary always runs `develop`. Changes reach the secondary through `develop` and the primary through `master`, so keep both branches aligned (merge `master` into `develop` after hotfixes, and `develop` into `master` for releases) and re-deploy the secondary after every alignment.

The secondary is a personal server of the owner with unrelated confidential services; treat it as least-privilege territory (see the agent rules).

**Production runbook (primary).**
- Containers: `sudo docker ps`; Compose project `docker`, files in `docker/docker-compose.prod.yml`; commands run from the repo root with `--env-file ./docker/.env`.
- Code is bind-mounted, so `git pull` changes the live files but processes keep the old code: restart what changed (`sudo docker restart docker-web-1` for API/Apache config, `docker-worker-1` and `docker-beat-1` for tasks/email code). Rebuild images (`./build.sh`) only when `Dockerfile.*` or `requirements.txt` change.
- Logs: app log is `private/logs/app.log` (rotated at midnight, 3 backups; both web and worker write there since `home=/app`). Celery/task output is in `sudo docker logs --tail N docker-worker-1` (can be huge: always use `--tail` + `grep`). The Apache logs of the API are inside `docker-web-1`; host `/var/log/apache2` is unrelated scanner noise.
- Health: `GET /health` (single `status`: ok/degraded/error/critical), `GET /version`, `sudo docker ps` shows `(healthy)` for redis/worker/autoheal. Queue depth: `sudo docker exec docker-redis-1 redis-cli llen priority` (Redis has a password; the container sets `REDISCLI_AUTH`). Worker liveness: `sudo docker exec docker-worker-1 celery -A make_celery.celery inspect ping`.
- Run git and edit files as the file owner (`ubuntu`, uid 1000): the worker/beat containers run as uid 1000 and root-owned files in `private/` break log rotation and writes.
- Published ports: web 443, MariaDB 3307 (needed by the secondary; restrict it to the secondary's IP if possible). Redis is not published.

## Git workflow (GitFlow, mandatory for every human and agent)

Follow GitFlow and general Git good practice. `master` = production (primary server), `develop` = integration (secondary server). Never commit directly to either; both only change through a **pull request**.

**Branches**
- New functionality: `feature/<short-name>`. Bug fix: `fix/<short-name>`. Urgent production failure: `hotfix/<short-name>`.
- `feature/*` and `fix/*` branch off `develop`. `hotfix/*` branches off `master`, is PR'd into `master`, and then `master` must be merged back into `develop` so the branches stay aligned.
- **One bug = one `fix/*` branch with its own commit(s).** Never fix several bugs in the same branch or the same commit, and never mix a fix with a feature or a refactor. Same for features: one purpose per branch.
- **Related set of tasks** (several related fixes or features): create an umbrella branch off `develop` (e.g. `feature/<topic>` or `fix/<topic>-batch`), then one sub-branch per fix/feature off the umbrella, each merged into the umbrella by PR (or a no-fast-forward merge). When the whole set is finished and verified, open **one PR umbrella → `develop`**. This way the `develop` CI/CD runs once per set, not once per small task, while every task keeps its own branch and commits.
- Test-only or docs-only changes also get their own branch (`feature/` or `fix/` by intent); do not hide them inside an unrelated branch.

**Commits and PRs**
- Small, atomic commits with Conventional Commit messages (`fix:`, `feat:`, `test:`, `docs:`, `chore:`, `refactor:`), imperative subject, body explaining *why*. Each commit should leave the tests passing.
- A fix commit includes its regression test. Do not rewrite history that is already pushed or shared (no force-push on shared branches); rebase/clean only your own unpushed work.
- Never commit secrets, `.env*`, DB dumps or anything under `private/` or `public/`.
- Every PR states what/why, how it was tested and its deployment impact (restart needed, migration, rebuild).

**Promotion path**
1. Feature/fix branch → PR into `develop` (CI runs) → deployed to the secondary and verified there.
2. Only when everything works on `develop`: PR `develop` → `master` (full CI incl. integration + real-services), then deploy to the primary.
3. **Deploying `master` affects production** (the salon and its customers). Do it only in **low-load hours**, outside the business's opening hours (confirm the window with the owner if unsure), never during peak booking times, and verify `/health`, `/version` and the worker right after (`scripts/smoke_test.sh`). A `hotfix/*` for an urgent outage may justify going outside that window, but only with the owner's explicit approval.
- Agents never merge a PR, push to `master`/`develop` or deploy without the user's explicit confirmation.

## Production lessons learned (read before debugging)

- **Paths depend on `os.getcwd()`.** Under mod_wsgi the daemon's cwd was `/home/apiuser`, so uploaded email templates were saved inside the web container while the worker read stale copies from `/app/public`. Fixed with `WSGIDaemonProcess ... home=/app` in `apache-flask.conf.template` (2026-10-21). Symptom to remember: "the URL shows the new template but emails use the old one" = web and worker are not reading the same directory.
- **Worker silently hung after Redis was recreated** (2026-10-16 to 2026-10-21): the `priority` queue grew (23 stuck emails) while the container showed "Up". Mitigations now in `master`: robust reconnect options in `celery_app/celery_config.py`, worker healthcheck (`celery inspect ping`) + `autoheal`, Redis healthcheck/AOF/noeviction. When emails stop, check `llen priority` and `inspect ping` first, then restart `docker-worker-1`; queued emails are delivered on restart (late ones too).
- `max_retries=12` with a 2 h delay (24 h) means an email can still be lost after a longer SMTP failure; there is no reconciliation job for bookings whose `email_*` flag is false. Consider one if touching this area.
- `helpers/EmailController.py` (`send_mail`) logs the SMTP password in clear text (`Pass: ...`). Do not paste those log lines anywhere; fixing it and rotating the Brevo key are pending.
- The `prod_changes` branch has an unpushed local commit containing a full DB dump (`private/db/backup.sql`). Never push database dumps, `.env` files or anything under `private/`.
- `develop` and the secondary's branch can lag behind `master`; hotfixes have been committed straight to `master`. Ask which branch to target before pushing.

## Private server configuration and the ops agent

Server access details (SSH targets, project paths, what each account may do) live in **`.claude/servers.local.md`**, which is gitignored; `.claude/servers.example.md` is the template. The project agent `booking-api-ops` (`.claude/agents/booking-api-ops.md`) reads that file and this document before touching production. Never commit credentials, `.env` files, SMTP passwords, tokens or DB dumps.

## Roadmap: pending tasks

Ordered roughly by priority. Treat each as a project of its own: propose a plan and get approval before touching production.

### Infrastructure and data

1. **Automatic database backups (critical) — implemented on `feature/db-backups`, pending review, deploy to the secondary (`develop`) and then to the primary (`master`); see "Database backups" above and `docs/db-backups.md` (deployment steps, including the one-off DB restart and the secondary's restricted account, need the owner's approval). Remaining after deploy: verify with a real restore test in production, remove the legacy `daily_worker` dump.** Original problem statement, kept for context: there is no real backup system. The only thing today is `daily_worker` (beat, `DAILY_HOUR:DAILY_MINUTE`, default 03:00) calling `helpers/Backup.py` `backup_all`, which runs one `mysqldump` into `private/db/backup.sql` on the same host (overwritten every day, no retention, no copy elsewhere; the upload step logs "Backup API is not set"). Needed: scheduled dumps with retention (e.g. daily/weekly/monthly), compression, off-server copy (the DB lives only on the primary), encryption of the copies, failure alerts, and a documented and *tested* restore procedure. Never write dumps inside the git tree (`private/` is gitignored but the `prod_changes` branch already leaked one).
2. **Data warehouse database.** The operational DB keeps every past booking forever and grows without limit, which will eventually exhaust disk space. Create a separate analytical/historical database (own schema, ETL job that moves or copies bookings older than a retention window, keeps the data needed for reporting, then purges them from the operational DB safely and idempotently). Decide retention, what stays operational (`booking`, `service_booking`, tokens) and how reports read the warehouse.
3. **Data cleanup jobs.** Expired rows are never removed: `session_token` rows for expired user/worker tokens (they accumulate on every booking email), old `closed` dates, stale `file` records, old rotated logs and `private/reports/fallback_reports.json`. Add Celery beat tasks (queue `default`) that delete in small batches, log what they remove and never delete tokens that are still valid or that back the JWT blocklist of live sessions.
4. **Observability stack: logs, metrics, health and alerts.** Today the only signals are `private/logs/app.log`, `docker logs` and `GET /health`. Implement a monitoring stack (e.g. Prometheus + Grafana + Loki/Promtail or an equivalent, plus Alertmanager) covering: centralized and searchable logs from both servers (with the SMTP password already redacted), container/host metrics, API latency and error rate, Celery queue depth (`priority`/`default`) and worker liveness, Redis and MariaDB health, disk usage, email delivery failures/provider caps, backup job success, and alerts to a channel the owners read (email/Telegram/etc.). Keep it light enough for the servers and do not expose its ports publicly; the secondary is a personal server, so deploy nothing there without the owner's approval.

### Security and reliability fixes found during incidents

5. **Stop logging the SMTP password.** `helpers/EmailController.py` `send_mail` logs `Pass: <password>` at INFO. Remove it from the log line, purge/rotate the old logs that contain it, and **rotate the Brevo SMTP key** (and any other provider key that appeared in logs).
6. **Never lose an email.** `send_mail_task` has `max_retries=12` with 2 h delays (24 h, raised from 3), then the task fails for good. Add a reconciliation beat task that re-queues bookings whose expected `email_*` flag is false (with a cap and de-duplication) and alerts when emails have been pending too long.
7. **Restrict the published MariaDB port (3307).** The secondary connects to the primary's DB over it; limit it with firewall rules to the secondary's IP (and consider TLS) instead of leaving it open.
8. **Disable SSH password authentication on the primary** (`PasswordAuthentication no`) once every account is confirmed to use keys; it is currently enabled while bots brute-force the host.
9. **Secrets hygiene on the secondary.** Several `.env*` files and `private/db/backup.sql` inside the project folder were world-readable (`644`/`664`), and an account for Isma exists there (see the restricted `booking-docker` wrapper above; he has no shell-level Docker access). Set them to `600` and rotate any secret that may have been exposed; review `.git` history for committed secrets.

### Repo and process housekeeping

10. **Branch cleanup.** Delete or neutralize the local `prod_changes` commit that contains a DB dump (never push it), and decide the branching model (`develop` vs straight-to-`master` hotfixes) so the deployed branches stay in sync.
11. **Update the tests and make the whole suite pass — done on branch `feature/test-suite` (2026-11-10), pending review/merge.** Result: `python -m pytest tests` = 337 passed, 3 failing on purpose (known app bugs b, c below); real-services tier 22 passed. Open items found while doing it: (a) `tests/integration/test_email.py` is flaky (waiter threads race the SMTP counter assertions), currently masked with `pytest.mark.flaky(reruns=2)`; split it into small tests with the waiter patched; (b) `resources/close.py` PUT/DELETE don't check the closed date belongs to the caller's local (failing test); (c) `resources/files.py:171` deletes gallery images with `IMAGE_TYPE_LOGOS`, so gallery deletion always 404s (failing test); (d) `celery_app/tasks.py` imports `DEBUG` from `logging` (always truthy); (e) `helpers/Database.py` has `from datetime import time`, shadowing the module (breaks the test-mode `register_key_value_cache`); (g) resilience tests (`tests/integration/services/test_zz_resilience_*`): Redis restarts, worker stop/SIGKILL and SMTP retries pass; the MariaDB-restart tests required `SQLALCHEMY_ENGINE_OPTIONS={'pool_pre_ping': True}` in `app.py` (fixed) — the cause of "emails stop after a DB restart"; (f) `db/init.sql` was missing a `;` and several columns/tables vs the models (fixed; verify the production schema matches the models too). Original description, kept for context: several recent changes (Redis password and resilient connections in `helpers/Database.py`, `/health` now returning `redis` status, `server_name` on bookings, `home=/app`) were made without running or updating `tests/`. Run `python -m pytest tests/`, fix or update outdated tests, add tests for the new behaviour (health/degraded, Redis failure paths, cleanup and backup tasks once they exist) and record the baseline result here.
12. **Implement CI/CD.** There is no pipeline. Add CI (e.g. GitHub Actions) running the test suite on every push/PR to `develop` and `master`, plus lint and a security scan for committed secrets. Then add CD: automatic deploy of `master` to the primary and `develop` to the secondary (SSH-based or pull-based), with image rebuild only when `Dockerfile.*`/`requirements.txt` change, container restarts, a post-deploy health check, automatic rollback on failure, and notifications. Secrets go in the CI secret store, never in the repo; deploying to the secondary needs the owner's explicit approval of the mechanism and its access scope.
13. **Multi-server booking lock.** The secondary has its own Redis, so the short slot lock is not shared across servers; only the DB overlap check protects against double bookings when both servers accept bookings. Evaluate whether this is acceptable or the lock should move to the shared DB.
