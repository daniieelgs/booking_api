# Testing

How to write tests per tier: skill `write-tests`. How to run everything and analyse failures: skill `test-bug-report`. Agent: `test-engineer`.

## Layout
- `tests/unit/`: no Flask app over HTTP; pure logic with mocks, `fakeredis` for the real `WATCH` semantics of the booking lock, and `tests/unit/db_support.py` `DbTestCase` (bare Flask + in-memory SQLite + JWT) for helpers that need `db.session`.
- `tests/integration/`: full Flask app over HTTP with SQLite (`flask_testing.TestCase`); no real DB/Redis.
- `tests/integration/services/` (marker `services`): real MariaDB 10.5.19 + Redis 7.2.4 + a Celery worker from `docker/docker-compose.test.yml`.
- `tests/backup/`: the `dbbackup/` suite (stdlib only) plus `tests/backup/e2e/run_e2e.sh` (real MariaDB/rsync/SSH/age in Docker; run it before merging changes to `dbbackup/`, `scripts/` or the compose file).
- Shared helpers stay in `tests/` (`config_test.py`, `configure_local_base.py`). `pytest.ini` deselects `services` by default. Keep `tests/__init__.py` empty so the backup suite stays independent of the Flask app.
- The root `conftest.py` sets `FLASK_DEBUG=1` before `globals` is imported (`REDIS_TEST_MODE`/`EMAIL_TEST_MODE` are only honoured with `DEBUG` on), so the suite never depends on a developer's `.env`.

## Commands (from the repo root)
- All, no Docker: `python -m pytest tests/`
- One file / test: `python -m pytest tests/integration/test_work_group.py::TestWorkGroup::test_method -v`
- Real-services tier: `docker compose -f docker/docker-compose.test.yml up -d --wait`, then `RUN_INTEGRATION_TESTS=1 python -m pytest tests/integration/services -m services -v` (run that directory on its own: `globals.py` binds env at import), then `docker compose -f docker/docker-compose.test.yml down -v`. See `tests/integration/services/README.md`.
- Email redelivery tests (`test_zz_email_redelivery.py`, marker `redelivery`): prefork Celery worker in a Linux container against the real Redis, scaled-down delays; about 25 min in all; needs the image `booking-exp-worker` (`docker build -f docker/Dockerfile.exp-worker -t booking-exp-worker .`). Local only: GitHub runs `-m "services and not redelivery"`.
- Post-deploy check: `scripts/smoke_test.sh --url <api> [--expect-version X] [--worker <container>]`.
- Don't run two pytest processes at once: the SQLite test DB (`instance/data_test.db`) is shared.
- Failing tests stay red: never `xfail`/`expectedFailure` (`check_tests.py` guards it).
- `TEST_PERFORMANCE=1` is a separate load-test mode that changes `app.py`'s startup path and API prefix (`tests/config_test_performance.py`, `resources/unavaliable_api.py`); don't confuse it with the normal suite.

## Fixture pattern
`flask_testing.TestCase`: `create_app()` returns `create_app(config_test)`; `setUp()` calls `db.create_all()` then `config_test.config(db=db)`; `tearDown()` calls `db.session.remove()`, `db.drop_all()`, `config_test.drop(self.locals)`. `tests/config_test.py` exposes `getUrl(*parts)` (prefixes `api/v1/`) and `setParams(url, **params)`.

## CI
`.github/workflows/tests.yml`: on push/PR to `develop` only the unit tests run; on `master` also SQLite integration + backup tests and the job `services` (real MariaDB/Redis/Celery in Docker) without `redelivery`. Paste the output of what you ran in every PR body (CI on `develop` is minimal).

## Python environment
Pinned `requirements.txt` needs Python 3.11 (`lxml==5.1.0`, `greenlet==3.0.2`; CI and `Dockerfile.base` use 3.11). Cloud sessions ship 3.13: if `.venv/` exists use `.venv/bin/python -m pytest ...`; otherwise `uv venv --python 3.11 .venv && uv pip install --python .venv/bin/python -r requirements.txt pytest` (a `SessionStart` hook in `.claude/settings.json` does it automatically). `requirements.txt` is UTF-16 encoded: never re-save it as UTF-8.
