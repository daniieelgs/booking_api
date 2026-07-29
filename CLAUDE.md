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
- Run prod stack: `docker-compose --env-file ./docker/.env -f ./docker/docker-compose.prod.yml up` (HTTPS via Apache + mod_wsgi, see `docker/docker-entrypoint.sh` and `apache-flask.conf.template`).

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
