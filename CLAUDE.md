# CLAUDE.md

Guía para Claude Code (claude.ai/code) en este repositorio. Mantén este fichero corto: contexto del proyecto, convenciones y enlaces. Los procedimientos van en los agentes y skills de abajo, los detalles en `docs/` y el trabajo pendiente en el backlog de GitHub (Issues + Project), nunca aquí.

## Proyecto

Backend de reservas multi-tenant ("locals" = negocios). Hoy hay un único cliente: **SUBLIME HAIR SALON** (web pública https://www.sublimebarberia.com/, backoffice del personal https://backend.sublimebarberia.com/; son dos frontends independientes que solo consumen esta API). Stack: Flask (flask-smorest), Celery, Redis, MariaDB, Docker. La lista completa de endpoints está en `/openapi.json` (Swagger UI solo con `FLASK_DEBUG=1`).

## Mapa: agentes, skills, docs, backlog

| Necesidad | Usar |
|---|---|
| Errores de producción, logs, emails que no llegan, despliegue, nuevas funcionalidades y arreglos de la app | agente **`booking-api-ops`** (contiene el runbook de producción) |
| Escribir/ejecutar tests, cazar bugs, re-verificar arreglos | agente **`test-engineer`** + skills **`write-tests`**, **`test-bug-report`** |
| Backlog, ramas, PR, higiene y ajustes del repo, PR de hotfix | agente **`scrum-master`** + skill **`backlog`** |
| Release `develop` → `master`: preparación, notas, checklist de despliegue | skill **`release`** |
| Añadir o cambiar un endpoint/recurso | skill **`new-endpoint`** |
| Revisión de seguridad de un diff/PR/zona (solo lectura) | agente **`security-reviewer`** |
| Mantener la documentación fiel al código, documentar funcionalidades, mantener corto este fichero | agente **`docs-keeper`** + skill **`docs-check`** |
| Trabajo pendiente (bugs, features, tareas, roadmap) | Issues + Project de GitHub de `daniieelgs/booking_api` (skill `backlog`) |
| Infraestructura, servidores, despliegue | `docs/infrastructure.md` |
| Garantías de entrega de email, plantillas, proveedores SMTP | `docs/email-system.md` |
| Estructura de tests, comandos, CI, entorno Python | `docs/testing.md` |
| Backups de la base de datos y restauración | `docs/db-backups.md` |
| Incidentes pasados | `docs/lessons-learned.md` |

El acceso privado a servidores (SSH, rutas, límites de cuenta) está en `.claude/servers.local.md` (ignorado por git; plantilla `servers.example.md`).

## Convención de idioma

- **En español**: todas las explicaciones y la documentación: cuerpo de los commits, descripción de PR e issues, `docs/`, `CLAUDE.md`, `changelog.md`, descripciones de Swagger (docstrings de los endpoints), comentarios del código y respuestas al usuario.
- **En inglés**: los nombres: ramas, asunto del commit (`fix: ...` en Conventional Commits), título de PR e issue, rutas y campos de los endpoints, identificadores del código, nombres de tests y los títulos de sección de las plantillas de issue (los scripts los leen). Los textos `message` de los `abort(...)` se mantienen como están para no romper a los frontends.
- Lo que aún esté en inglés se traduce cuando se toque (agente `docs-keeper`).

## Comandos

Todos desde la raíz del repo (`booking_api/`): las rutas de ficheros se construyen con `os.getcwd()`, ejecutar desde otro sitio rompe el almacenamiento de imágenes, logs e informes.

- Preparación: `.env` en la raíz (ver `.env.example`), más `docker/.env` y `db/.env` para Docker. `pip install -r requirements.txt` (Python 3.11; el fichero está en **UTF-16**, nunca lo guardes como UTF-8).
- Ejecutar: `flask run` o `python app.py` (ambos usan `create_app()` de `app.py`).
- Migraciones (Flask-Migrate; `migrations/` está en `.gitignore`, ejecuta `flask db init` una vez por entorno): `flask db migrate -m "..."` y `flask db upgrade`.
- Celery: `celery -A make_celery.celery worker --loglevel=info -Q priority,default` y `celery -A make_celery.celery beat --loglevel=info`.
- Token de admin: `python access.py --generate <días> --name <nombre>` (`--help` para más).
- Docker: build con `./build.sh` o `./build.ps1`; dev `docker-compose --env-file ./docker/.env -f ./docker/docker-compose.yml up`; prod `docker compose --env-file ./docker/.env -f ./docker/docker-compose.prod.yml up -d` (detalles y el fichero de entorno distinto del secundario en `docs/infrastructure.md`).
- Tests: `python -m pytest tests/` (sin Docker). Niveles, nivel de servicios, redelivery, CI y entorno Python en `docs/testing.md`. No ejecutes dos procesos pytest a la vez.

## Arquitectura

- **Factoría de app, sin estructura de paquete.** `create_app(config)` de `app.py` registra los blueprints y conecta JWT/Celery/CORS/logging; `wsgi.py` y `make_celery.py` importan el `app` construido a nivel de módulo allí (se omite si `TEST_PERFORMANCE` está activo: es un modo aparte de pruebas de carga, no la suite normal).
- **Capas de configuración.** `config.py` (`Config`) ← `default_config.py` (desde `globals.py`) ← `tests/config_test.py` / `tests/config_test_performance.py`. `create_app()` recibe una instancia de config para que los tests la sustituyan.
- **`globals.py` es la única fuente de configuración de entorno** (`DEFAULT_X = ...` y luego `X = os.getenv('X', DEFAULT_X)`), además del logger global y de `log(...)` (estructurado, con caché por uuid). Añade ahí las constantes nuevas. Si un valor debe poder cambiarse en ejecución (tests), léelo con `os.getenv()` dentro de una función en vez de fijarlo al importar (ver `helpers/path.py`, `helpers/ReportController.py`).
- **Versiones.** `API_VERSION` (`'v1'`) es la etiqueta de URL/OpenAPI; `VERSION` en `globals.py` es la versión de release que devuelve `GET /version`. No las confundas.
- **Recursos = blueprints de flask-smorest, un fichero por dominio** en `resources/`, registrados con un prefijo de `getApiPrefix()` (`api/v1`). Excepciones: `public_files.py` (`/public`) y `status.py` (`/health`, `/version`) en la raíz. Patrón: `MethodView` + `@blp.route`, `@blp.arguments(Schema)`, `@blp.response(code, description=...)` apilados para los errores más un 2xx con el schema, docstring = descripción de Swagger. Todos los schemas en `schema.py`.
- **Auth, tres mecanismos mezclados según el endpoint:** (1) `@jwt_required(refresh=True|fresh=True)`, identidad = id del local; (2) comprobación manual del token de admin (`helpers/security.py` `check_admin_token()`/`check_admin_request()`, `resources/admin.py`) contra `SessionTokenModel` + `ADMIN_ROLE`; (3) sin decorador = público (`public_files.py`, `status.py`, GET públicos de `work_group.py`/`service.py`, el endpoint fallback de `report.py`, que acepta JSON arbitrario a propósito). Los tokens de sesión son revocables (`SessionTokenModel` es la lista de bloqueo JWT, `token_in_blocklist_loader` en `app.py`).
- **Códigos de estado:** `401` credenciales ausentes/inválidas/caducadas; `403` autenticado pero sin permiso (datos de otro local, un worker haciendo algo solo de local); `404` el recurso no existe para ese local.
- **`@log_route`** (`helpers/LoggingMiddleware.py`) envuelve la mayoría de handlers: inyecta `_uuid`, registra petición/respuesta y convierte las excepciones no controladas en un 500 JSON (y las relanza). Los handlers aceptan `_uuid=None` al final.
- **Acceso a BD mediante los helpers de `db.py`** (`addAndCommit`, `deleteAndCommit`, `addAndFlush`, `deleteAndFlush`, `commit`, `rollback`), nunca `db.session` directo; rellenan `datetime_created/updated`.
- **Errores de dominio** en `helpers/error/<Domain>Error/`, una clase por fichero; los handlers hacen `abort(code, message=str(e) if DEBUG else '<genérico>')`, nunca filtran internos con `DEBUG` apagado.
- **El almacenamiento de ficheros es disco local bajo `os.getcwd()`**: `helpers/path.py` (`PUBLIC_FOLDER`, releído en cada llamada) y `helpers/ReportController.py` (lock de hilo + lock de fichero del SO, seguro con varios procesos).
- **Celery:** `make_celery()` en `celery_app/celery_config.py`, tareas en `celery_app/tasks.py`, schedule de beat definido en línea dentro de `create_app()`.
- **Zona horaria:** todo `datetime` ingenuo de la BD es hora local de reloj en la zona del propio local (`LocalModel.location`): localízalo con `naiveToAware(value, local.location)` y compara con `now(local.location)`. Los instantes absolutos (`exp` del JWT) usan UTC explícito. Ver `helpers/DatetimeHelper.py`.

## Reglas de negocio

- **Flujo del cliente (sin registro):** elige servicio, opcionalmente un worker (si no, el backend asigna uno), un hueco libre, y rellena nombre/email/teléfono. Email de confirmación opcional solo si `local_settings.booking_timeout` (minutos) está definido; si no se confirma, se autocancela con `check_booking_status`; `NULL`/`-1` lo desactiva (**desactivado para Sublime**: las reservas pasan directas a confirmadas). Después, email de "confirmada" con un enlace con token de usuario (válido hasta que acaba la reserva) para cancelar (existe la modificación, pero está **desactivada para Sublime**); cancelar/modificar envían su propio email.
- **Backoffice:** solo inician sesión los workers de un local (`/api/v1/local/login`): historial y próximas reservas, cancelar reservas, gestionar servicios, horarios, días cerrados, workers y sus servicios.
- **Niveles de auth / roles:** público, local/worker (JWT), usuario (token del email, solo su reserva), admin. Roles `A` admin, `L` local, `U` usuario. Estado de reserva `P` pendiente, `C` confirmada, `D` hecha, `X` cancelada.
- **Un worker nunca puede tener dos reservas solapadas.** Capa 1: lock Redis de corta duración por local (`waitAndRegisterBooking`/`perform_atomic_booking` en `helpers/BookingController.py`, `WATCH` + `SETEX`, clave = `local_id`, caducidad `MAX_TIMEOUT_WAIT_BOOKING`). Capa 2: la BD es la fuente de verdad (`getBookings(...)` comprueba solapes `C`/`P` antes de insertar). El secundario tiene su propio Redis, así que solo la capa 2 abarca ambos servidores.
- **Toda reserva debe acabar con su email**, incluso con caídas de SMTP o reinicios: mantén la cola duradera (Redis AOF, `noeviction`) y no descartes tareas en silencio. Detalles en `docs/email-system.md`.
- **Modelo de datos** (una tabla por concepto): `booking`, `closed`, `file`, `local`, `local_settings`, `service`, `session_token`, `smtp_settings`, `timetable`, `worker`, `work_group` (un local puede tener varios, cada uno con sus servicios y workers); tablas de unión `service_booking`, `work_group_worker`; tablas de catálogo `status`, `weekday`.

## Infraestructura (resumen)

Dos servidores, mismo código, ambos sobre la **misma MariaDB (en el primario)**. Primario = `master`, API principal + BD + contenedor de backup; secundario = `develop`, API de respaldo con su propio Redis/Celery. El código está montado por bind, así que tras un `git pull` hay que reiniciar contenedores. `GET /health` → `ok`/`degraded`/`error`/`critical`. Backups de BD: dump nocturno + binlog PITR + copia cifrada al secundario (`dbbackup/`, `docs/db-backups.md`). Todo lo demás: `docs/infrastructure.md`; operaciones: `booking-api-ops`.

## Reglas de seguridad

- Nunca subas ni pegues secretos: `.env*`, tokens, contraseñas SMTP/BD/Redis, volcados de BD, nada de `private/` ni `public/`. El repositorio es **público**: issues, PR, commits y docs no pueden contener secretos, datos de clientes, logs de producción en bruto ni direcciones de servidores.
- No expongas detalles internos de errores con `DEBUG` apagado; respeta la semántica `401`/`403`/`404` de arriba; comprueba la propiedad (`local_id`) en cada recurso de un local.
- Sin acceso a producción desde sesiones desatendidas/cloud (sin `servers.local.md` ni credenciales de `booking-db`): no pidas ni inventes credenciales. Producción, SSH y despliegues los hace el dueño o una sesión que él supervise.
- Los agentes nunca fusionan una PR, hacen push a `master`/`develop`, despliegan, cambian ajustes del repo ni ejecutan comandos destructivos de BD/Redis sin confirmación explícita del usuario.
- Desplegar `master` afecta a los clientes del salón: solo en horas de baja carga, fuera del horario de apertura; verifica después con `scripts/smoke_test.sh`.

## Flujo Git (GitFlow, obligatorio para personas y agentes, en local o en cloud)

`master` = producción (primario), `develop` = integración (secundario). Nunca hagas commit directo en ninguna; solo cambian mediante **pull request**.

- Ramas desde `develop`: `feature/<nombre>`, `fix/<nombre>`; `hotfix/<nombre>` desde `master` (PR a `master` y luego merge de `master` a `develop`; los rulesets permiten al admin saltárselos solo mediante una PR, con aprobación explícita del dueño; el agente `scrum-master` la prepara). Empieza con `git fetch origin && git switch -c <tipo>/<nombre> origin/develop`; si el entorno creó otra rama, cambia a una correcta antes de commitear. El prefijo `claude/` solo si el entorno rechaza cualquier otro (`claude/feature-<nombre>`, dilo en la PR).
- **Una issue/bug = una rama = una PR** con sus propios commits; nunca mezcles un arreglo con una funcionalidad o un refactor. Conjunto de tareas relacionadas: rama paraguas desde `develop`, una subrama por tarea fusionada en ella y una PR paraguas → `develop`. Los cambios solo de tests o solo de docs también tienen su propia rama.
- **Toda PR enlaza su issue** (`Closes #n` en el cuerpo; el workflow `close-linked-issues` la cierra al fusionar en `develop`) y sigue `.github/pull_request_template.md`: qué/por qué, salida real de tests, impacto en el despliegue. Abre la PR hacia `develop` (nunca `master`).
- Commits Conventional pequeños y atómicos (`fix:`, `feat:`, `test:`, `docs:`, `chore:`, `refactor:`), asunto en inglés e imperativo, cuerpo en español que explica el porqué; un arreglo incluye su test de regresión. No reescribas el historial de ramas ya subidas y compartidas.
- **Sube `VERSION` en `globals.py`** (SemVer: fix → patch, feature → minor, breaking → major) cuando cambie el comportamiento o la API; las PR solo de docs/tests no. Una vez por PR paraguas.
- Ejecuta `python -m pytest tests/` antes de abrir la PR (y el nivel de servicios si tocas BD/Redis/Celery/reservas/email y hay Docker); pega los resultados en la PR.
- Promoción: feature/fix → PR a `develop` → verificado en el secundario → PR `develop` → `master` (CI completo) → despliegue en el primario en horas de baja carga.
- Si un test falla sin causa clara o un requisito es ambiguo, para y avisa; nunca marques un test fallido como fallo esperado. Los bugs que encuentres mientras haces otra cosa van al backlog (skill `backlog`) en lugar de arreglarlos en línea.
- Los procedimientos (abrir ramas/PR, releases, limpieza de ramas, ajustes del repo) los ejecuta el agente `scrum-master`.

## Sesiones cloud

Mismas reglas, sin un flujo más ligero. Cloud trae Python 3.13 pero los requirements fijados necesitan 3.11: usa `.venv/bin/python -m pytest ...` (un hook `SessionStart` en `.claude/settings.json` lo crea; ver `docs/testing.md`). Los hallazgos deben sobrevivir a la sesión: `private/` está en `.gitignore` y no existe en cloud, así que los bugs van al backlog (issues) y a la descripción de la PR.

## Agentes y skills

- Agentes (`.claude/agents/`): `booking-api-ops` (app + producción), `test-engineer` (QA), `scrum-master` (backlog/ramas/PR/hotfixes en GitHub), `security-reviewer` (revisión de seguridad de solo lectura), `docs-keeper` (documentación).
- Skills (`.claude/skills/`): `backlog` (Issues/etiquetas/tablero de GitHub; scripts `issue.py`, `setup_repo.py`), `write-tests` (convenciones de tests por nivel, guarda `check_tests.py`), `test-bug-report` (ejecuta todos los niveles, analiza fallos en `private/reports/tests/*.json` + HTML, publica/enlaza bugs al backlog), `new-endpoint` (checklist de convenciones + plantilla), `release` (`release_check.py`: preparación y notas), `docs-check` (`check_docs.py`: referencias rotas, presupuesto de tamaño).
- Cuando una tarea tenga un agente o skill que sabe hacerla, no describas aquí el procedimiento: ponlo en el agente/skill.
