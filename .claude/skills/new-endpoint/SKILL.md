---
name: new-endpoint
description: Añade o cambia un endpoint REST (o un recurso/dominio completo) en la Booking API siguiendo las convenciones del proyecto - modelo, schema de Marshmallow, blueprint de flask-smorest, registro en app.py, comprobaciones de propiedad, manejo de errores, tests (incluidos los cross-local), changelog e incremento de versión. Úsala cuando te pidan "añade un endpoint", "expón X en la API", "crea un nuevo recurso/CRUD", "añade un campo a la API", o al revisar que un endpoint nuevo sigue las convenciones.
---

# Nuevo endpoint

Trabaja a partir de un issue en una rama `feature/*` desde `develop` (skill `backlog`, GitFlow en `CLAUDE.md`). Un conjunto de endpoints = un propósito = un PR.

## Lista de comprobación (en orden)

1. **Lee primero a los vecinos.** Abre el recurso existente más cercano en `resources/` (`work_group.py` es un ejemplo limpio de CRUD), su modelo en `models/` y sus schemas en `schema.py`. Copia su estilo, no la memoria de este fichero.
2. **Modelo** (`models/<name>.py`, exportado en `models/__init__.py`): `db.Model`, columnas `datetime_created`/`datetime_updated`, FK `local_id` para todo lo que pertenezca a un local, `UniqueConstraint` donde los nombres deban ser únicos por local. Un cambio de esquema necesita un plan de migración: dilo en el issue/PR (`flask db migrate`, y actualiza `db/init.sql`).
3. **Schemas** en `schema.py` (fichero monolítico único): `required=True, dump_only=True` para ids/marcas de tiempo, `validate=` para longitudes/rangos, un `...ListSchema` (base `ListSchema`) para colecciones. Nunca expongas secretos ni datos de otros locales; usa un `Public...Schema` aparte para las rutas públicas.
4. **Recurso** en `resources/<domain>.py`, un `Blueprint` por dominio, clases `MethodView` con `@blp.route`. Pila de decoradores: `@blp.arguments(Schema)` (+ `location='query'` para parámetros), `@blp.response(code, description=...)` para cada error que el handler pueda devolver, luego un único `@blp.response(2xx, Schema)`, y después el decorador de auth. Docstring = descripción de Swagger. Ver `references/template.md`.
5. **Auth y propiedad** (la fuente de bugs más común aquí):
   - Datos de ámbito local: `@jwt_required(refresh=True)` (o `fresh=True` para acciones destructivas); identidad = `get_jwt_identity()` = id del local.
   - Solo admin: la comprobación artesanal de `helpers/security.py`.
   - Público: sin decorador, y solo datos públicos.
   - **Toda** búsqueda de un recurso por id debe verificar `resource.local_id == get_jwt_identity()` (`403` si no, `404` si no existe). Comprueba también los ids padre e hijo (un worker de otro local dentro de mi work group).
6. **Errores:** `401` credenciales, `403` no permitido, `404` no existe, `409` conflictos (`IntegrityError`), `500` ante `SQLAlchemyError` con `message = str(e) if DEBUG else '<generic>'` tras `rollback()`. Los errores de dominio van en `helpers/error/<Domain>Error/`, una clase por fichero. Nunca filtres detalles internos cuando `DEBUG` esté desactivado.
7. **Acceso a BD** solo mediante los helpers de `db.py` (`addAndCommit`, `deleteAndCommit`, ...). Los datetimes naive son hora de pared en la zona horaria del local (`naiveToAware`, `now(local.location)`).
8. **Los handlers que hacen trabajo real** (reservas, emails, cualquier cosa con efectos secundarios) se envuelven con `@log_route` (aceptan `_uuid=None`). Los cambios de reservas deben mantener las garantías de solapamiento (`getBookings`, lock de Redis): lee las reglas de negocio de `CLAUDE.md`.
9. **Registra** el blueprint en `app.py` (`api.register_blueprint(X, url_prefix=getApiPrefix('<name>'))`).
10. **Tests** (skill `write-tests`, agente `test-engineer`): fichero de tests de integración `tests/integration/test_<domain>.py` (401 sin token, camino feliz, validación 422, 404, 409, 403 para datos de otro local) y añade el caso cross-local a `tests/integration/test_cross_local_ownership.py`. Ejecuta `python -m pytest tests/ -q` y el nivel de servicios si toca BD/Redis/Celery/emails.
11. **Documentación del contrato:** añade el endpoint a `changelog.md` (método, ruta, formato de petición/respuesta) porque los dos frontends (web del cliente y backoffice) lo consumen; menciona los cambios que rompen compatibilidad en el PR.
12. **Versión:** incrementa `VERSION` en `globals.py` (endpoint nuevo = minor, cambio incompatible = major) una vez por PR/paraguas.
13. **Antes del PR:** ejecuta el agente `security-reviewer` sobre el diff, y `docs-keeper` si cambió el comportamiento o las operaciones.

## Qué no hacer
- No añadas un segundo fichero de schemas, llamadas directas a `db.session` ni valores de entorno fijados en el código (usa `globals.py`).
- No devuelvas `200` con un cuerpo de error; usa `abort(code, message=...)`.
- No cambies la forma de una respuesta existente sin avisar a los frontends (changelog + nota en el PR).
