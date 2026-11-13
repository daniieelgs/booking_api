# Infrastructure

Two servers, same codebase, both read/write the **same MariaDB (on the primary)**. Access details (SSH targets, paths, what each account may do) are private: `.claude/servers.local.md` (gitignored; template `.claude/servers.example.md`). The production runbook (commands, logs, health checks) lives in the `booking-api-ops` agent (`.claude/agents/booking-api-ops.md`).

| | Primary `booking-api.es` | Secondary `booking-api.ddns.net` |
|---|---|---|
| Role | Main API + the database | Fallback when the primary is down or a booking returns 500; the frontend then posts a report to `POST /api/v1/report/fallback` |
| Stack | Docker Compose prod: `web` (`booking-flask`, Apache + mod_wsgi, terminates SSL), `database` (`mariadb:10.5.19`), `worker` + `beat` (`booking-base`, Celery), `redis` (`redis:7.2.4-bookworm`), `backup`, `autoheal` | Docker; `flask run --port 5001` (Werkzeug), own Celery worker/beat and own Redis, DB = primary's published port |
| Git branch deployed | `master` | `develop` |

**Branch per server (by design):** the primary always runs `master`; the secondary always runs `develop`. Changes reach the secondary through `develop` and the primary through `master`, so keep both branches aligned (merge `master` into `develop` after hotfixes, `develop` into `master` for releases) and re-deploy the secondary after every alignment. The secondary can lag behind `master`: check before assuming parity.

The secondary is a personal server of the owner with unrelated confidential services: treat it as least-privilege territory.

## Primary (production)
- Compose project `docker` (folder `docker/`), files `docker/docker-compose.prod.yml`, run from the repo root with `--env-file ./docker/.env`. Container names `docker-web-1`, `docker-worker-1`, ... Only Compose v2 (`docker compose`) is installed.
- Code is bind-mounted as `/app` in every container, so `git pull` changes the live files but processes keep the old code: restart what changed. Rebuild images (`./build.sh`) only when `Dockerfile.*` or `requirements.txt` change.
- Published ports: web 443, MariaDB 3307 (needed by the secondary). Redis is not published.
- Redis is the Celery broker/result backend and the booking lock store: it runs with AOF + `--maxmemory-policy noeviction`, a password and a named volume (`redis-data`). It must not lose or evict data.
- The `prod` DB service runs with binlogs enabled for point-in-time recovery (see `docs/db-backups.md`).

## Secondary
- Docker there is the snap package (socket `/var/run/docker.sock` is `root:docker`; the snap assigns that group each time `dockerd` starts, so no manual `chgrp` should be needed; if it ever shows `root root`, run `sudo snap disable docker && sudo snap enable docker`, which restarts every container on that host).
- Start the stack with the secondary's own env file, **not** `docker/.env` (that one is the prod config: Apache/SSL, port 442, and crash-loops the web container): `docker compose --env-file ./docker/.env2 -f ./docker/docker-compose.yml up -d` (`PORT=5001`, `FLASK_ENV=development`, `REDIS_PORT=6378`, plus `REDIS_PASSWORD`, which must also be in `.env` and inside `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND`).
- Public traffic reaches it through 443 (a front proxy); port 5001 is not reachable from outside.
- Other unrelated projects share that Docker daemon: only touch containers named `docker-*`; never restart the snap or other compose projects.
- It has its **own** Redis, so the booking lock does not span both servers; only the DB overlap check does (tracked in the backlog).

### Restricted Docker access for the project developer (secondary)
The developer account has no `docker` group and no general sudo. They run `sudo booking-docker <action>`, a root-owned wrapper (`/usr/local/bin/booking-docker`, allowed by `/etc/sudoers.d/booking-docker`) that only accepts `ps` (lists the `docker-*` containers of this project), `logs <container> [1-2000 lines]` and `restart <container>` (only `docker-web-1`, `docker-worker-1`, `docker-beat-1`). Anything else is rejected; container names are a hard-coded allow-list. **These two files live only on the secondary and are intentionally not in the repo**; if container names or the project path change, edit the wrapper there with `sudo`.

## Health endpoint
`GET /health` returns only `{"status": ...}` (always HTTP 200): `ok` (database, Redis and a Celery worker answering), `degraded` (worker down: bookings work, emails delayed), `error` (Redis down: no bookings) or `critical` (database down); worst failure wins (`helpers/HealthController.py`; worker ping cached `HEALTH_CACHE_SECONDS`=10 s, timeout `HEALTH_WORKER_TIMEOUT`=1 s). `GET /version` returns `VERSION` from `globals.py`.

## Compose files
`docker/docker-compose.yml` (dev, also used by the secondary), `docker/docker-compose.prod.yml`, `docker/docker-compose.test.yml` (real-services test tier). Build images with `./build.sh` or `./build.ps1`.
