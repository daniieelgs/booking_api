---
name: new-endpoint
description: Add or change a REST endpoint (or a whole resource/domain) in the Booking API following the project's conventions - model, Marshmallow schema, flask-smorest blueprint, registration in app.py, ownership checks, error handling, tests (including cross-local), changelog and version bump. Use when asked to "add an endpoint", "expose X in the API", "create a new resource/CRUD", "add a field to the API", or when reviewing that a new endpoint follows the conventions.
---

# New endpoint

Work from an issue on a `feature/*` branch off `develop` (skill `backlog`, GitFlow in `CLAUDE.md`). One endpoint set = one purpose = one PR.

## Checklist (in order)

1. **Read the neighbours first.** Open the closest existing resource in `resources/` (`work_group.py` is a clean CRUD example), its model in `models/` and its schemas in `schema.py`. Copy their style, not this file's memory.
2. **Model** (`models/<name>.py`, exported in `models/__init__.py`): `db.Model`, `datetime_created`/`datetime_updated` columns, `local_id` FK for anything owned by a local, `UniqueConstraint` where names must be unique per local. A schema change needs a migration plan: say so in the issue/PR (`flask db migrate`, and update `db/init.sql`).
3. **Schemas** in `schema.py` (single monolithic file): `required=True, dump_only=True` for ids/timestamps, `validate=` for lengths/ranges, a `...ListSchema` (`ListSchema` base) for collections. Never expose secrets or other locals' data; use a separate `Public...Schema` for public routes.
4. **Resource** in `resources/<domain>.py`, one `Blueprint` per domain, `MethodView` classes with `@blp.route`. Decorator stack: `@blp.arguments(Schema)` (+ `location='query'` for params), `@blp.response(code, description=...)` for every error the handler can return, then one `@blp.response(2xx, Schema)`, then the auth decorator. Docstring = Swagger description. See `references/template.md`.
5. **Auth and ownership** (the most common source of bugs here):
   - Local-scoped data: `@jwt_required(refresh=True)` (or `fresh=True` for destructive actions); identity = `get_jwt_identity()` = local id.
   - Admin-only: hand-rolled check from `helpers/security.py`.
   - Public: no decorator, and only public data.
   - **Every** lookup of a resource by id must verify `resource.local_id == get_jwt_identity()` (`403` if not, `404` if it does not exist). Check parent and child ids too (a worker of another local inside my work group).
6. **Errors:** `401` credentials, `403` not allowed, `404` does not exist, `409` conflicts (`IntegrityError`), `500` on `SQLAlchemyError` with `message = str(e) if DEBUG else '<generic>'` after `rollback()`. Domain errors go in `helpers/error/<Domain>Error/`, one class per file. Never leak internals when `DEBUG` is off.
7. **DB access** only through `db.py` helpers (`addAndCommit`, `deleteAndCommit`, ...). Naive datetimes are wall-clock in the local's timezone (`naiveToAware`, `now(local.location)`).
8. **Handlers that do real work** (bookings, emails, anything with side effects) wrap with `@log_route` (accept `_uuid=None`). Booking changes must keep the overlap guarantees (`getBookings`, Redis lock): read `CLAUDE.md` business rules.
9. **Register** the blueprint in `app.py` (`api.register_blueprint(X, url_prefix=getApiPrefix('<name>'))`).
10. **Tests** (skill `write-tests`, agent `test-engineer`): integration test file `tests/integration/test_<domain>.py` (401 without token, happy path, validation 422, 404, 409, 403 for another local's data) and add the cross-local case to `tests/integration/test_cross_local_ownership.py`. Run `python -m pytest tests/ -q` and the services tier if it touches DB/Redis/Celery/emails.
11. **Contract docs:** add the endpoint to `changelog.md` (method, path, request/response format) because the two frontends (customer site and backoffice) consume it; mention breaking changes in the PR.
12. **Version:** bump `VERSION` in `globals.py` (new endpoint = minor, breaking = major) once per PR/umbrella.
13. **Before the PR:** run the `security-reviewer` agent on the diff, and `docs-keeper` if behaviour or operations changed.

## Don'ts
- Don't add a second schema file, raw `db.session` calls, or hard-coded env values (use `globals.py`).
- Don't return `200` with an error body; use `abort(code, message=...)`.
- Don't change an existing response shape without telling the frontends (changelog + PR note).
