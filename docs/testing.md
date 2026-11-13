# Tests

Cómo escribir tests por nivel: skill `write-tests`. Cómo ejecutarlo todo y analizar fallos: skill `test-bug-report`. Agente: `test-engineer`.

## Estructura
- `tests/unit/`: sin la app Flask sobre HTTP; lógica pura con mocks, `fakeredis` para la semántica real de `WATCH` del lock de reservas, y `tests/unit/db_support.py` `DbTestCase` (Flask mínimo + SQLite en memoria + JWT) para helpers que necesitan `db.session`.
- `tests/integration/`: app Flask completa sobre HTTP con SQLite (`flask_testing.TestCase`); sin BD ni Redis reales.
- `tests/integration/services/` (marcador `services`): MariaDB 10.5.19 + Redis 7.2.4 + un worker de Celery reales desde `docker/docker-compose.test.yml`.
- `tests/backup/`: la suite de `dbbackup/` (solo librería estándar) más `tests/backup/e2e/run_e2e.sh` (MariaDB/rsync/SSH/age reales en Docker; ejecútalo antes de fusionar cambios en `dbbackup/`, `scripts/` o el compose).
- Los helpers compartidos se quedan en `tests/` (`config_test.py`, `configure_local_base.py`). `pytest.ini` deselecciona `services` por defecto. Mantén vacío `tests/__init__.py` para que la suite de backup siga independiente de la app Flask.
- El `conftest.py` de la raíz fija `FLASK_DEBUG=1` antes de importar `globals` (`REDIS_TEST_MODE`/`EMAIL_TEST_MODE` solo se respetan con `DEBUG` activo), así la suite nunca depende del `.env` de quien la ejecuta.

## Comandos (desde la raíz del repo)
- Todo, sin Docker: `python -m pytest tests/`
- Un fichero / un test: `python -m pytest tests/integration/test_work_group.py::TestWorkGroup::test_method -v`
- Nivel de servicios reales: `docker compose -f docker/docker-compose.test.yml up -d --wait`, después `RUN_INTEGRATION_TESTS=1 python -m pytest tests/integration/services -m services -v` (ejecuta ese directorio solo: `globals.py` fija el entorno al importar), y por último `docker compose -f docker/docker-compose.test.yml down -v`. Ver `tests/integration/services/README.md`.
- Tests de reentrega de email (`test_zz_email_redelivery.py`, marcador `redelivery`): worker Celery prefork en un contenedor Linux contra el Redis real, con esperas reducidas; unos 25 min en total; necesita la imagen `booking-exp-worker` (`docker build -f docker/Dockerfile.exp-worker -t booking-exp-worker .`). Solo en local: GitHub ejecuta `-m "services and not redelivery"`.
- Comprobación tras desplegar: `scripts/smoke_test.sh --url <api> [--expect-version X] [--worker <contenedor>]`.
- No ejecutes dos procesos pytest a la vez: la BD SQLite de tests (`instance/data_test.db`) es compartida.
- Los tests que fallan se quedan en rojo: nunca `xfail`/`expectedFailure` (lo vigila `check_tests.py`).
- `TEST_PERFORMANCE=1` es un modo aparte de pruebas de carga que cambia el arranque de `app.py` y el prefijo de la API (`tests/config_test_performance.py`, `resources/unavaliable_api.py`); no lo confundas con la suite normal.

## Patrón de fixtures
`flask_testing.TestCase`: `create_app()` devuelve `create_app(config_test)`; `setUp()` llama a `db.create_all()` y luego a `config_test.config(db=db)`; `tearDown()` llama a `db.session.remove()`, `db.drop_all()`, `config_test.drop(self.locals)`. `tests/config_test.py` expone `getUrl(*parts)` (antepone `api/v1/`) y `setParams(url, **params)`.

## CI
`.github/workflows/tests.yml`: en push/PR a `develop` solo corren los tests unitarios; en `master` también los de integración con SQLite, los de backup y el job `services` (MariaDB/Redis/Celery reales en Docker) sin `redelivery`. Pega la salida de lo que hayas ejecutado en el cuerpo de cada PR (el CI de `develop` es mínimo).

## Entorno Python
El `requirements.txt` fijado necesita Python 3.11 (`lxml==5.1.0`, `greenlet==3.0.2`; el CI y `Dockerfile.base` usan 3.11). Las sesiones cloud traen 3.13: si existe `.venv/` usa `.venv/bin/python -m pytest ...`; si no, `uv venv --python 3.11 .venv && uv pip install --python .venv/bin/python -r requirements.txt pytest` (un hook `SessionStart` en `.claude/settings.json` lo hace solo). `requirements.txt` está en UTF-16: nunca lo guardes como UTF-8.
