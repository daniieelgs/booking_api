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
- Tests use `flask_testing.TestCase` (unittest-style), not pytest fixtures, and default to a local SQLite DB (`TEST_DATABASE_URI`) — no real DB/Redis needed.
- Run all: `python -m pytest tests/` (or `python -m unittest discover tests`)
- Run one file: `python -m pytest tests/test_work_group.py -v`
- Run one test: `python -m pytest tests/test_work_group.py::TestWorkGroup::test_method -v` (or `python -m unittest tests.test_work_group.TestWorkGroup.test_method`)
- A separate "performance test" mode exists (`TEST_PERFORMANCE=1` env var), which changes `app.py`'s startup path and API prefix — see `tests/config_test_performance.py` and `resources/unavaliable_api.py`. Don't confuse it with the normal test suite.

## Architecture

**App factory, no package layout.** Everything hangs directly off the repo root (no top-level `__init__.py`). `app.py`'s `create_app(config)` builds the Flask app, registers all blueprints, and wires JWT/Celery/CORS/logging; `wsgi.py` and `make_celery.py` both import the already-built `app` object from `app.py` (module-level `app = create_app()` runs at import time unless `TEST_PERFORMANCE` is set).

**Config layering.** `config.py` (`Config`, plain data holder) ← `default_config.py` (`DefaultConfig`, populates `Config` from `globals.py`) ← `tests/config_test.py` (`ConfigTest`, points at SQLite, seeds `UserSessionModel`/`StatusModel`/`WeekdayModel`, mints an `ADMIN_TOKEN`) / `tests/config_test_performance.py` (`ConfigTestPerformance`, similar but for load-testing). `create_app()` takes a `Config` instance so tests can swap in `ConfigTest` without touching `app.py`.

**`globals.py` is the single source of truth for environment config.** Every setting follows `DEFAULT_X = ...` then `X = os.getenv('X', DEFAULT_X)`. It also owns the global logger (`setLogger`/`getLogger`), the app singleton (`setApp`/`getApp`), and the `log(message, level, uuid, request, response, error, save_cache)` function used everywhere for structured logging (keeps a per-uuid cache and flushes it on a background thread when `save_cache=True`). Add new env-driven constants here, following the existing pattern — unless the value needs to be overridable at runtime (e.g. in tests), in which case read it via `os.getenv()` inside a getter function instead of binding it as a module-level constant at import time (see `getReportsFile()`/`getMaxReportSize()` in `helpers/ReportController.py` vs. the plain `PUBLIC_FOLDER` handled the same way in `helpers/path.py`).

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

A worker can never have two overlapping bookings. Two layers: (1) `waitAndRegisterBooking`/`perform_atomic_booking` in `helpers/BookingController.py` take a short-lived Redis lock per local (`WATCH` + `SETEX`, key = `local_id`, expiry `MAX_TIMEOUT_WAIT_BOOKING`) so two concurrent requests cannot take the same slot; (2) the DB is the source of truth — `getBookings(...)` checks overlaps for `C`/`P` bookings before inserting. Redis connection helpers live in `helpers/Database.py` (pooled, retry with backoff, password from `REDIS_PASSWORD`). Redis is also the Celery broker/result backend, so **Redis must not lose or evict data**: it runs with AOF + `--maxmemory-policy noeviction`, a password, and a named volume (`redis-data`). `/health` reports `degraded` when Redis does not answer. Note: the secondary server has its **own** Redis, so the lock does not span both servers — only the DB overlap check does.

## Email system

- Sent by Celery task `send_mail_task` (queue `priority`, `max_retries=3`, retry delay `60 * RETRY_SEND_EMAIL` seconds = 2 h by default) in `celery_app/tasks.py`; rendering/sending in `helpers/EmailController.py`. `check_booking_status` and `daily_worker` (backup at `DAILY_HOUR:DAILY_MINUTE`, default 03:00) run on queue `default`; beat schedules only `daily_worker`.
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

**Branch per server (by design):** the primary always runs `master`; the secondary always runs `develop`. Changes reach the secondary through `develop` and the primary through `master`, so keep both branches aligned (merge `master` into `develop` after hotfixes, and `develop` into `master` for releases) and re-deploy the secondary after every alignment.

The secondary is a personal server of the owner with unrelated confidential services; treat it as least-privilege territory (see the agent rules).

**Production runbook (primary).**
- Containers: `sudo docker ps`; Compose project `docker`, files in `docker/docker-compose.prod.yml`; commands run from the repo root with `--env-file ./docker/.env`.
- Code is bind-mounted, so `git pull` changes the live files but processes keep the old code: restart what changed (`sudo docker restart docker-web-1` for API/Apache config, `docker-worker-1` and `docker-beat-1` for tasks/email code). Rebuild images (`./build.sh`) only when `Dockerfile.*` or `requirements.txt` change.
- Logs: app log is `private/logs/app.log` (rotated at midnight, 3 backups; both web and worker write there since `home=/app`). Celery/task output is in `sudo docker logs --tail N docker-worker-1` (can be huge: always use `--tail` + `grep`). The Apache logs of the API are inside `docker-web-1`; host `/var/log/apache2` is unrelated scanner noise.
- Health: `GET /health` (status + redis), `GET /version`, `sudo docker ps` shows `(healthy)` for redis/worker/autoheal. Queue depth: `sudo docker exec docker-redis-1 redis-cli llen priority` (Redis has a password; the container sets `REDISCLI_AUTH`). Worker liveness: `sudo docker exec docker-worker-1 celery -A make_celery.celery inspect ping`.
- Run git and edit files as the file owner (`ubuntu`, uid 1000): the worker/beat containers run as uid 1000 and root-owned files in `private/` break log rotation and writes.
- Published ports: web 443, MariaDB 3307 (needed by the secondary; restrict it to the secondary's IP if possible). Redis is not published.

## Production lessons learned (read before debugging)

- **Paths depend on `os.getcwd()`.** Under mod_wsgi the daemon's cwd was `/home/apiuser`, so uploaded email templates were saved inside the web container while the worker read stale copies from `/app/public`. Fixed with `WSGIDaemonProcess ... home=/app` in `apache-flask.conf.template` (2026-10-21). Symptom to remember: "the URL shows the new template but emails use the old one" = web and worker are not reading the same directory.
- **Worker silently hung after Redis was recreated** (2026-10-16 to 2026-10-21): the `priority` queue grew (23 stuck emails) while the container showed "Up". Mitigations now in `master`: robust reconnect options in `celery_app/celery_config.py`, worker healthcheck (`celery inspect ping`) + `autoheal`, Redis healthcheck/AOF/noeviction. When emails stop, check `llen priority` and `inspect ping` first, then restart `docker-worker-1`; queued emails are delivered on restart (late ones too).
- `max_retries=3` with a 2 h delay means an email can still be lost after prolonged SMTP failure; there is no reconciliation job for bookings whose `email_*` flag is false. Consider one if touching this area.
- `helpers/EmailController.py` (`send_mail`) logs the SMTP password in clear text (`Pass: ...`). Do not paste those log lines anywhere; fixing it and rotating the Brevo key are pending.
- The `prod_changes` branch has an unpushed local commit containing a full DB dump (`private/db/backup.sql`). Never push database dumps, `.env` files or anything under `private/`.
- `develop` and the secondary's branch can lag behind `master`; hotfixes have been committed straight to `master`. Ask which branch to target before pushing.

## Private server configuration and the ops agent

Server access details (SSH targets, project paths, what each account may do) live in **`.claude/servers.local.md`**, which is gitignored; `.claude/servers.example.md` is the template. The project agent `booking-api-ops` (`.claude/agents/booking-api-ops.md`) reads that file and this document before touching production. Never commit credentials, `.env` files, SMTP passwords, tokens or DB dumps.

## Roadmap: pending tasks

Ordered roughly by priority. Treat each as a project of its own: propose a plan and get approval before touching production.

### Infrastructure and data

1. **Automatic database backups (critical).** There is no real backup system. The only thing today is `daily_worker` (beat, `DAILY_HOUR:DAILY_MINUTE`, default 03:00) calling `helpers/Backup.py` `backup_all`, which runs one `mysqldump` into `private/db/backup.sql` on the same host (overwritten every day, no retention, no copy elsewhere; the upload step logs "Backup API is not set"). Needed: scheduled dumps with retention (e.g. daily/weekly/monthly), compression, off-server copy (the DB lives only on the primary), encryption of the copies, failure alerts, and a documented and *tested* restore procedure. Never write dumps inside the git tree (`private/` is gitignored but the `prod_changes` branch already leaked one).
2. **Data warehouse database.** The operational DB keeps every past booking forever and grows without limit, which will eventually exhaust disk space. Create a separate analytical/historical database (own schema, ETL job that moves or copies bookings older than a retention window, keeps the data needed for reporting, then purges them from the operational DB safely and idempotently). Decide retention, what stays operational (`booking`, `service_booking`, tokens) and how reports read the warehouse.
3. **Data cleanup jobs.** Expired rows are never removed: `session_token` rows for expired user/worker tokens (they accumulate on every booking email), old `closed` dates, stale `file` records, old rotated logs and `private/reports/fallback_reports.json`. Add Celery beat tasks (queue `default`) that delete in small batches, log what they remove and never delete tokens that are still valid or that back the JWT blocklist of live sessions.
4. **Observability stack: logs, metrics, health and alerts.** Today the only signals are `private/logs/app.log`, `docker logs` and `GET /health`. Implement a monitoring stack (e.g. Prometheus + Grafana + Loki/Promtail or an equivalent, plus Alertmanager) covering: centralized and searchable logs from both servers (with the SMTP password already redacted), container/host metrics, API latency and error rate, Celery queue depth (`priority`/`default`) and worker liveness, Redis and MariaDB health, disk usage, email delivery failures/provider caps, backup job success, and alerts to a channel the owners read (email/Telegram/etc.). Keep it light enough for the servers and do not expose its ports publicly; the secondary is a personal server, so deploy nothing there without the owner's approval.

### Security and reliability fixes found during incidents

5. **Stop logging the SMTP password.** `helpers/EmailController.py` `send_mail` logs `Pass: <password>` at INFO. Remove it from the log line, purge/rotate the old logs that contain it, and **rotate the Brevo SMTP key** (and any other provider key that appeared in logs).
6. **Never lose an email.** `send_mail_task` has `max_retries=3` with 2 h delays, then the task fails for good. Add a reconciliation beat task that re-queues bookings whose expected `email_*` flag is false (with a cap and de-duplication) and alerts when emails have been pending too long.
7. **Align `develop` with `master`, re-deploy the secondary and test.** The primary runs `master`, the secondary runs `develop`, and `develop` is ~10 commits behind (Redis password/resilience, worker reconnect, `home=/app`, healthcheck). Merge `master` into `develop`, push, then re-deploy the secondary together with the owner (its `.env` needs a `REDIS_PASSWORD` matching its own Redis, rebuild/restart containers as needed). Afterwards test end to end on the secondary: `/health`, a test booking, email delivery, worker `inspect ping`, and the fallback report flow from the frontend.
8. **Restrict the published MariaDB port (3307).** The secondary connects to the primary's DB over it; limit it with firewall rules to the secondary's IP (and consider TLS) instead of leaving it open.
9. **Disable SSH password authentication on the primary** (`PasswordAuthentication no`) once every account is confirmed to use keys; it is currently enabled while bots brute-force the host.
10. **Secrets hygiene on the secondary.** Several `.env*` files and `private/db/backup.sql` inside the project folder were world-readable (`644`/`664`), and a read-only account for Isma exists there. Set them to `600` and rotate any secret that may have been exposed; review `.git` history for committed secrets.

### Repo and process housekeeping

11. **Branch cleanup.** Delete or neutralize the local `prod_changes` commit that contains a DB dump (never push it), and decide the branching model (`develop` vs straight-to-`master` hotfixes) so the deployed branches stay in sync.
12. **Keep agent docs in sync.** `AGENTS.md` (untracked copy for Codex) is outdated relative to this file: either update it from `CLAUDE.md` or remove it. Remove the leftover `backup/pages_pre_fix_20261021` folder on the primary once the template fix is confirmed.
13. **Update the tests and make the whole suite pass.** Several recent changes (Redis password and resilient connections in `helpers/Database.py`, `/health` now returning `redis` status, `server_name` on bookings, `home=/app`) were made without running or updating `tests/`. Run `python -m pytest tests/`, fix or update outdated tests, add tests for the new behaviour (health/degraded, Redis failure paths, cleanup and backup tasks once they exist) and record the baseline result here.
14. **Implement CI/CD.** There is no pipeline. Add CI (e.g. GitHub Actions) running the test suite on every push/PR to `develop` and `master`, plus lint and a security scan for committed secrets. Then add CD: automatic deploy of `master` to the primary and `develop` to the secondary (SSH-based or pull-based), with image rebuild only when `Dockerfile.*`/`requirements.txt` change, container restarts, a post-deploy health check, automatic rollback on failure, and notifications. Secrets go in the CI secret store, never in the repo; deploying to the secondary needs the owner's explicit approval of the mechanism and its access scope.
15. **Multi-server booking lock.** The secondary has its own Redis, so the short slot lock is not shared across servers; only the DB overlap check protects against double bookings when both servers accept bookings. Evaluate whether this is acceptable or the lock should move to the shared DB.
