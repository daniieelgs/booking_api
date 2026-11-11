# Integration tests against real services

These tests run the app against the same versions as production: MariaDB `10.5.19` (schema, triggers and seeds
from `db/init.sql`), Redis `7.2.4` with a password, and a real Celery worker on the `priority,default` queues.
Only the SMTP socket is faked (`email_test_mode`). All credentials are throw-away test values.

## Run locally

Shortcut (with the project venv activated; it uses the `python` on the PATH): starts the containers, runs all the
services tests and always removes the containers and volumes at the end, even if the tests fail. Extra arguments go
straight to pytest, and the exit code is pytest's.

```powershell
.\scripts\run_services_tests.ps1                              # Windows PowerShell
.\scripts\run_services_tests.ps1 -k redis -x
```

```bash
scripts/run_services_tests.sh                                  # Linux / macOS / Git Bash
scripts/run_services_tests.sh -m "services and not resilience"
```

The manual steps below do the same by hand.

Docker must be running; the compose stack is **not** started by the tests (CI does it in the workflow).

Git Bash / Linux / macOS:

```bash
docker compose -f docker/docker-compose.test.yml up -d --wait
RUN_INTEGRATION_TESTS=1 python -m pytest tests/integration/services -m services -v
docker compose -f docker/docker-compose.test.yml down -v
```

Windows PowerShell (the `VAR=value command` form does not exist there; set the variable with `$env:`):

```powershell
docker compose -f docker/docker-compose.test.yml up -d --wait
$env:RUN_INTEGRATION_TESTS = "1"
.\.venv\Scripts\python.exe -m pytest tests/integration/services -m services -v
docker compose -f docker/docker-compose.test.yml down -v
Remove-Item Env:RUN_INTEGRATION_TESTS   # the variable stays set in that window until removed
```

(`.\.venv\Scripts\python.exe` is the project venv; with it activated, plain `python` works too.)

### Run a single test or a subset

Always keep `-m services`: `pytest.ini` adds `-m "not services"` by default, so naming a services file without it
deselects everything. Quote `file::test[id]` in PowerShell (the brackets are special there).

```powershell
# one file
python -m pytest tests/integration/services/test_redis_lock.py -m services -v
# one test (file::name)
python -m pytest "tests/integration/services/test_redis_lock.py::test_locals_do_not_block_each_other" -m services -v
# one parametrized case (the id goes in brackets)
python -m pytest "tests/integration/services/test_zz_resilience_worker.py::test_tasks_queued_while_the_worker_is_down_run_when_it_starts_again[sigkill]" -m services -v
# by name (-k accepts and / or / not)
python -m pytest tests/integration/services -m services -k "redis" -v
python -m pytest tests/integration/services -m services -k "health and not redis_down" -v
# only the slow resilience tests, or everything except them
python -m pytest tests/integration/services -m "services and resilience" -v
python -m pytest tests/integration/services -m "services and not resilience" -v
```

The suites without Docker need no `-m` nor environment variable, and the same selection syntax applies:

```powershell
python -m pytest tests/unit -v
python -m pytest tests/integration/test_close.py::TestClose::test_other_local_cannot_delete_a_close_day -v
python -m pytest tests/integration -k "health" -v
```

Useful flags: `-x` stop at the first failure, `--lf` rerun only the last failures, `-s` show prints/logs live,
`--collect-only -q` list what would run, `-W ignore` hide deprecation warnings.

Never run two pytest processes at once (shared SQLite file for the non-services tiers, shared containers here), and
never combine `tests/integration/services` with other test folders in the same command.

- **Run this directory on its own.** `globals.py` binds the database/Redis/Celery settings at import time, so the
  environment set by `conftest.py` only takes effect if nothing imported `globals` before it. Mixing it with
  `tests/unit` or `tests/integration` in one pytest run points the other tests at the wrong services.
- A plain `python -m pytest tests/` never runs these (`pytest.ini` excludes the `services` marker, and without
  `RUN_INTEGRATION_TESTS=1` they are skipped anyway).
- `conftest.py` refuses to run if `globals` does not point at `127.0.0.1:3317` / `127.0.0.1:6380`, e.g. because a
  local `.env` overrides the test settings, so these tests can never touch a development or production database.
- `test_zz_health_redis_down.py` and `test_zz_resilience_*.py` stop/restart the Redis and MariaDB containers and kill Celery workers on purpose; do not run these tests in parallel. Deselect the slow ones with `-m "services and not resilience"`.
- The Celery worker log is written to `celery-worker.log` (gitignored) and shown when the worker fails to start; the resilience tests write `celery-worker-resilience-N.log` next to it.

## What is covered

| File | Proves |
|---|---|
| `test_version_smoke.py` | MariaDB/Redis versions are the production ones; `db/init.sql` has every table, trigger, seed, and no column missing or shorter than the SQLAlchemy models |
| `test_redis_lock.py` | The real `WATCH`-based lock lets exactly one contender win a slot under concurrency |
| `test_booking_concurrency.py` | Concurrent HTTP bookings of the same worker and slot create exactly one row in MariaDB |
| `test_celery_roundtrip.py` | A task goes through the real broker to a real worker that reads and writes MariaDB |
| `test_health.py`, `test_zz_health_*.py` | `/health` is `ok` with database, Redis and worker up; `degraded` without worker, `error` with Redis stopped, `critical` with MariaDB stopped (HTTP 200 always), and each recovers |
| `test_zz_resilience_redis.py` | API keeps booking and the worker keeps consuming after Redis restarts (no process restart); an email queued while the worker is down survives a Redis restart (AOF, like production) |
| `test_zz_resilience_worker.py` | Tasks queued while the worker is down (graceful stop or SIGKILL) run when it starts again; a confirmation email is retried through real Celery retries until the (simulated) SMTP recovers |
| `test_zz_resilience_database.py` | API and worker keep working after a MariaDB restart (`pool_pre_ping` in `app.py`; without it the pooled connections die and emails stop until the processes are restarted) |
