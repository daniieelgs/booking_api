# Recetas por nivel

Contenido: [Unitarios](#unitarios) · [Unitarios con BD](#unitarios-con-bd-en-memoria) · [Integración](#integración-sqlite) ·
[Servicios reales](#servicios-reales-docker) · [Backup](#backup) · [Cómo ejecutar](#cómo-ejecutar)

Todos los comandos desde la raíz del repo y con el python del venv (`.venv/Scripts/python.exe` en Windows). La raíz tiene
`conftest.py` que pone `FLASK_DEBUG=1` antes de importar `globals` (así `REDIS_TEST_MODE`/`EMAIL_TEST_MODE` se respetan sin depender
del `.env` de nadie) y `pytest.ini` que excluye por defecto el marcador `services`.

## Unitarios

`tests/unit/test_<modulo>.py`, `unittest.TestCase` (o funciones pytest), una clase por función o grupo coherente.

Qué suele hacer falta:
- **Parchear donde se usa el nombre**: `mock.patch.object(EmailController, 'send_mail')`, no donde se define. Con `from x import now`, el nombre vive en el módulo que lo importa.
- **Reloj**: `mock.patch.object(BookingController, 'now', return_value=MADRID.localize(datetime(2030, 1, 15, 12)))`.
- **Redis**: `fakeredis` tiene `WATCH` real; dos clientes sobre un mismo `FakeServer` simulan dos procesos. Ejemplo en `tests/unit/test_booking_controller_atomic.py`.
- **Objetos del dominio**: `types.SimpleNamespace` con solo los campos que usa la función; no hace falta BD.
- **Entorno**: `mock.patch.dict(os.environ, {...})`; los módulos que leen el entorno al importar (`globals.py`) hay que parchearlos en el módulo que usa la constante (`mock.patch.object(Database, 'REDIS_HOST', 'x')`).
- **Ficheros**: directorio temporal + `os.chdir` con `addCleanup` (las rutas se construyen con `os.getcwd()`), ver `tests/unit/test_path.py`.
- **Marshmallow**: `Schema().load(data)` con `assertRaises(ValidationError)`; ver `tests/unit/test_schemas.py`.

```python
import unittest
from unittest import mock

from helpers import EmailController


class TestSomething(unittest.TestCase):

    def setUp(self):
        patcher = mock.patch.object(EmailController, 'send_mail', return_value=True)
        self.sent = patcher.start()
        self.addCleanup(patcher.stop)          # siempre addCleanup, aunque el test falle

    def test_it_does_the_expected_thing(self):
        result = EmailController.algo(...)

        self.assertTrue(result)
        self.sent.assert_called_once_with(...)
```

Un test por comportamiento: `test_returns_false_when_there_are_no_providers`, `test_falls_back_to_the_next_provider`, etc.
Para varios valores del mismo caso usa `self.subTest(value=...)`.

## Unitarios con BD en memoria

`tests/unit/db_support.py` ofrece `DbTestCase`: Flask mínimo (sin blueprints), SQLite en memoria, JWT y semillas de roles, estados y
días de la semana. No usa `flask_testing` ni `create_app()`: es rápido y no abre HTTP. Las claves foráneas no se aplican en SQLite, así que puedes usar `local_id='local-1'` sin crear el local.

```python
from db import db
from models.closed import ClosedModel
from tests.unit.db_support import DbTestCase


class TestGetClosedDays(DbTestCase):

    def test_returns_only_the_days_of_that_local(self):
        mine = ClosedModel(datetime_init=..., datetime_end=..., local_id='local-1')
        db.session.add(mine); db.session.commit()

        self.assertEqual([c.id for c in getClosedDays('local-1')], [mine.id])
```

Si el modelo nuevo no está en `db_support.py`, importa su módulo ahí (todos los modelos deben importarse antes de `create_all()`).
Para tokens: `generateTokens(identity, local_id, user_role=...)` crea el JWT y su fila en `session_token`.

## Integración (SQLite)

`tests/integration/test_<recurso>.py`. Flask completo por HTTP con `flask_testing.TestCase`. Redis y SMTP van en modo test (diccionario y `True`).
Es el patrón de todos los tests existentes (`test_close.py`, `test_files.py`, `test_admin.py`):

```python
import json

from flask_testing import TestCase

from app import create_app, db
from tests.config_test import config_test, getUrl, setParams
from tests.configure_local_base import LocalBase


class TestAlgo(TestCase):

    def create_app(self):
        app = create_app(config_test)
        self.locals = []
        return app

    def setUp(self):
        db.create_all()
        config_test.config(db=db)
        self.admin_token = config_test.ADMIN_TOKEN
        base = LocalBase(self.client, self.admin_token, self.assertEqual)
        base.create_local(-1, set_local_settings=False, set_smtp_settings=False)   # -1: sin timeout de confirmación
        self.locals.extend(base.locals)
        self.local = base                       # base.refresh_token es el token del local

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        config_test.drop(self.locals)           # borra carpetas public/ creadas

    def bearer(self, token=None):
        return {'Authorization': f'Bearer {token or self.local.refresh_token}'}

    def post_algo(self, payload, token=None):   # helpers pequeños por endpoint, no tests gigantes
        return self.client.post(getUrl('algo'), data=json.dumps(payload), headers=self.bearer(token),
                                content_type='application/json')

    def test_requires_authentication(self):
        r = self.client.post(getUrl('algo'), data='{}', content_type='application/json')

        self.assertEqual(r.status_code, 401)
```

Qué probar en un endpoint nuevo: sin token (401), token de otro rol (401/403), **recurso de otro local (403/404: es el fallo de
seguridad más fácil de introducir)**, validación del cuerpo (422), recurso inexistente (404), caso feliz con el efecto en BD,
conflictos (409). Para un segundo local, mira `create_other_local()` en `tests/integration/test_close.py`.

Cosas que conviene saber:
- `getUrl(...)` antepone `api/v1/`; `/health` y `/version` cuelgan de la raíz (`self.client.get('/health')`).
- Los tests comparten el SQLite `instance/data_test.db`: **no ejecutes dos pytest a la vez**.
- Para parchear un colaborador del endpoint (por ejemplo `resources.status.ping_redis`) parchea el nombre en el módulo del recurso.
- Si necesitas simular un fallo de SMTP, parchea `helpers.EmailController.send_mail` (en modo test devuelve `True` antes de abrir el socket) o la función de envío de `celery_app.tasks`.
- Tareas de Celery: `send_mail_task.apply(args=[...])` o llamarla directamente las ejecuta en el proceso, sin broker (ver `tests/integration/test_send_mail_task.py`).

## Servicios reales (Docker)

`tests/integration/services/`. Marcador `services` obligatorio: `pytestmark = pytest.mark.services`. Se ejecutan contra
`docker/docker-compose.test.yml` (MariaDB 10.5.19 en el puerto 3317, Redis 7.2.4 con AOF en el 6380) con `RUN_INTEGRATION_TESTS=1`.
`conftest.py` fija el entorno **antes** de importar `globals` y aborta si no apunta a esos puertos: por eso esta carpeta se ejecuta sola.

Piezas ya hechas (reutilízalas, no las dupliques):
- `config_integration.py`: `build_app()`, `db_query()`, `db_execute()`, `redis_client()`, `mint_admin_token()`, `delete_test_locals()`.
- `resilience_support.py`: fixtures `app` y `local` (local de prueba con servicios, horarios y SMTP), `worker_factory` (workers de Celery que el test puede parar, matar y arrancar), `restart_service()`, `wait_until()`, `book()`, `create_pending_booking()`, `wait_for_status()`, `wait_for_email()`.
- `conftest.py`: fixture `celery_worker` (un worker real por módulo) y `compose(...)` para `docker compose` sobre el stack de test.
- `worker_app_flaky.py`: worker cuyo envío de correo falla las N primeras veces (SMTP caído simulado).

```python
import pytest

from tests.integration.services.resilience_support import (app, create_pending_booking, local, restart_service,  # noqa: F401
                                                           redis_answers, wait_for_status, worker_factory)

pytestmark = [pytest.mark.services, pytest.mark.resilience]   # resilience: para tests lentos que paran/reinician servicios


def test_worker_keeps_consuming_after_redis_restarts(app, local, worker_factory):
    from celery_app.tasks import check_booking_status     # importar dentro: globals ya tiene el entorno de test
    worker = worker_factory().start()
    ...
    restart_service('redis', redis_answers)
    ...
    assert wait_for_status(booking_id, 'X', timeout=90), worker.log_text()[-2000:]   # el log ayuda a diagnosticar
```

Reglas:
- Un test que **para un contenedor** lo vuelve a levantar en `finally`, y se llama `test_zz_*.py` para que se ejecute al final. Nunca en paralelo.
- Esperas con `wait_until`/`wait_for_*` con tiempo máximo y mensaje de fallo útil; nada de `time.sleep` fijos.
- Concurrencia: `threading.Barrier` + `ThreadPoolExecutor`, ver `test_redis_lock.py` y `test_booking_concurrency.py`.
- Usa claves únicas en Redis y borra lo que crees; los locales de prueba se borran con `delete_test_locals`.
- Los fixtures importados llevan `# noqa: F401` (pytest los encuentra por nombre).
- Si añades una dependencia de BD (tabla o columna) que el test necesita, `db/init.sql` debe tenerla: el test de esquema `test_version_smoke.py` compara con los modelos.
- Sin la variable `RUN_INTEGRATION_TESTS=1` los tests se saltan solos; eso no es un `skip` tuyo, es el mecanismo del `conftest.py`.

Ejecutar (Docker Desktop debe estar arrancado; los tests **no** levantan el stack):

```powershell
.\scripts\run_services_tests.ps1 -k nombre -x        # Windows: levanta, ejecuta y elimina los contenedores
```
```bash
scripts/run_services_tests.sh -k nombre -x           # Linux / Git Bash
```

## Backup

`tests/backup/`, solo biblioteca estándar, **sin importar nada de la app Flask**; `tests/__init__.py` debe seguir vacío para que no se importe
la app. Mira los ficheros existentes (`test_scheduler.py`, `test_prune.py`…) y su `helpers.py` antes de escribir.
El e2e con Docker (`bash tests/backup/e2e/run_e2e.sh`) solo se ejecuta si se toca `dbbackup/`, `scripts/` o el compose.

## Cómo ejecutar

```powershell
# un archivo / un test / por nombre (comillas por los corchetes y ::)
python -m pytest tests/unit/test_security.py -q -W ignore
python -m pytest "tests/unit/test_security.py::TestEncryption::test_roundtrip" -q
python -m pytest tests/unit -k "closed and not expired" -q
python -m pytest tests/integration/test_close.py -q                 # integración: ~1-2 s por archivo pequeño
python -m pytest tests/backup -q
```

Servicios: ver arriba. En cada ejecución mira el **resumen y los nombres de los que fallan**, no solo el código de salida.
Útiles: `-x` (parar al primer fallo), `--lf` (repetir los que fallaron), `-s` (ver prints/logs), `--collect-only -q` (qué se ejecutaría).
