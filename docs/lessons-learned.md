# Production lessons learned (read before debugging)

- **Paths depend on `os.getcwd()`.** Under mod_wsgi the daemon's cwd was `/home/apiuser`, so uploaded email templates were saved inside the web container while the worker read stale copies from `/app/public`. Fixed with `WSGIDaemonProcess ... home=/app` in `apache-flask.conf.template` (2026-10-21). Symptom: "the URL shows the new template but emails use the old one" = web and worker are not reading the same directory.
- **Worker silently hung after Redis was recreated** (2026-10-16 to 2026-10-21): the `priority` queue grew (23 stuck emails) while the container showed "Up". Mitigations in `master`: robust reconnect options in `celery_app/celery_config.py`, worker healthcheck (`celery inspect ping`) + `autoheal`, Redis healthcheck/AOF/noeviction. When emails stop, check `llen priority` and `inspect ping` first, then restart `docker-worker-1`; queued emails are delivered on restart (late ones too).
- **Emails stopped after a MariaDB restart**: fixed with `SQLALCHEMY_ENGINE_OPTIONS={'pool_pre_ping': True}` in `app.py`.
- **`send_mail` used to log the SMTP password in clear text.** Code fixed (F-012); logs written before the fix still contain it and the provider keys must be rotated (backlog issue). Never paste old log lines anywhere.
- **Never push database dumps, `.env` files or anything under `private/`.** A local-only branch once got a commit with a full dump; it must never be pushed (backlog issue tracks its removal).
- **Hotfixes have been committed straight to `master`**, so `develop` and the secondary can lag: align the branches and ask which branch to target before pushing.
- `db/init.sql` had missing columns/tables (fixed there); the production schema vs. models comparison is tracked in the backlog.
