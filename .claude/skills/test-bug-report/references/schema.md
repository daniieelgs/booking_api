# Formatos de `private/reports/tests/`

Tres ficheros. Los dos JSON son la fuente de verdad; el HTML es solo una vista.

```
private/reports/tests/
├── results.json     números y resultado de cada test (lo escriben los scripts)
├── findings.json    el análisis: qué falla, dónde, por qué, cómo arreglarlo (lo escribes tú, Claude)
└── report.html      vista para humanos, generada por build_report.py
```

`private/` está en `.gitignore`: nada de esto se sube al repositorio.

## results.json (lo escriben `run_tests.py` y `recheck.py`; no lo edites a mano)

```json
{
  "schema": 1,
  "generated_at": "2026-11-11T18:30:00+01:00",
  "git": {"branch": "feature/test-suite", "commit": "a1b2c3d", "dirty": true},
  "python": "3.12.7",
  "tiers": {
    "unit": {
      "label": "Unitarios",
      "status": "ran",                       // "ran" | "not_run"
      "stale": false,                        // true: no se midió ahora, son números de una ejecución anterior
      "reason": "...",                       // solo si not_run
      "measured_at": "2026-11-11T18:30:00+01:00",
      "command": "python -m pytest tests/unit ...",
      "duration_seconds": 7.1,
      "counts": {"total": 289, "passed": 280, "failed": 9, "skipped": 0, "deselected": 0},
      "tests":    {"tests/unit/test_x.py::TestY::test_z": "passed" | "failed" | "error" | "skipped" | "xfailed" | "xpassed"},
      "failures": {"tests/unit/test_x.py::TestY::test_z": {
          "message": "AssertionError: ...", "traceback": "...últimas líneas...",
          "test_path": "tests/unit/test_x.py", "test_line": 42,        // último frame dentro de tests/
          "code_path": "helpers/closed.py", "code_line": 16,           // frame más profundo en el código de la app (si la excepción nace ahí)
          "crash_path": "...", "crash_line": 715}}                     // donde saltó la excepción (a veces unittest/una librería)
    },
    "integration": {...}, "services": {...}, "backup": {...}
  }
}
```

Niveles: `unit` (`tests/unit`), `integration` (`tests/integration`, SQLite), `services` (`tests/integration/services`,
Docker), `backup` (`tests/backup`). `code_path`/`code_line` (si existen) son el mejor punto de partida: el frame más profundo dentro del código de la
aplicación. `test_path`/`test_line` es la línea del test que falló. `crash_*` es donde saltó la excepción y puede ser el
helper de aserciones de unittest o una librería.

## findings.json (lo escribes tú)

```json
{
  "schema": 1,
  "updated_at": "2026-11-11T18:40:00+01:00",
  "findings": [ { ...finding... } ]
}
```

Cada hallazgo:

| Campo | Tipo | Contenido |
|---|---|---|
| `id` | string | `F-001`, `F-002`... estable: no renumeres al añadir o arreglar. |
| `kind` | `"test_failure"` \| `"extra"` \| `"backlog"` | `test_failure`: hay tests que fallan por esto. `extra`: hallazgo del análisis de código sin test que falle. `backlog`: bug que ya está en el backlog de GitHub (id `B-<nº de issue>`), importado por `findings.py sync-backlog`; no lo escribes tú. |
| `issue` | `{number, url, state}` \| ausente | Issue de GitHub vinculada (`state`: `open`/`closed`). La ponen `findings.py publish`, `link` y `sync-backlog`. El cuerpo de la issue lleva `<!-- finding: F-xxx -->` para poder re-vincularla. |
| `severity` | `critical` \| `high` \| `medium` \| `low` | Impacto real: seguridad entre locales/pérdida de datos o de correos = alta o crítica. |
| `tier` | `unit` \| `integration` \| `services` \| `backup` \| `null` | Nivel de los tests (`null` en `extra`). |
| `title` | string | Una línea, en el idioma del usuario. |
| `tests` | string[] | node ids completos de pytest que fallan por este bug (`[]` en `extra`). `recheck.py` los vuelve a ejecutar. |
| `test_description` | string | Qué comprueba el test, en lenguaje llano (escenario y resultado esperado). |
| `bug_description` | string | Qué hace mal el código y qué efecto tiene. |
| `root_cause` | string | Por qué ocurre, a nivel de código (la línea o el razonamiento exacto). |
| `evidence` | `[{type, text, file?, line?}]` | Lo observado: mensaje de la aserción, traza recortada, fragmento de código, salida de un experimento. `type`: `assertion`, `traceback`, `code`, `observation`, `experiment`. |
| `affected_files` | `[{path, lines, note?}]` | Rutas relativas al repo y líneas (`"42"` o `"42-60"`), tras comprobarlas con Read en el estado actual. |
| `suggested_fix` | `{summary, steps?, snippet?}` | Arreglo concreto. `snippet` opcional con el código propuesto. |
| `change_size` | `small` \| `medium` \| `discuss` | `small`: pocas líneas, sin decisiones. `medium`: varias funciones o falta una regla de negocio. `discuss`: toca diseño, arquitectura, modelo de datos o convenciones transversales: hay que comentarlo con el usuario antes. |
| `discuss_reason` | string \| null | Obligatorio si `change_size` es `discuss`; opcional si es `medium` y hay una decisión pendiente. |
| `status` | `open` \| `fixed` \| `wontfix` | `fixed` lo pone `recheck.py` cuando todos sus tests pasan (o `findings.py status` en los `extra`). |
| `status_updated_at` | ISO | |
| `latest_failure` | `{test, message, crash_path, crash_line, at}` \| `null` | Lo rellenan los scripts cuando sigue fallando. |
| `history` | `[{at, event}]` | Registro de cambios de estado. |
| `related` | string[] | ids de hallazgos relacionados. |

Al escribir un hallazgo piensa en quien lo lea sin contexto (otro agente que va a arreglarlo): debe poder localizar
el código, entender el porqué y saber cómo verificarlo (`recheck.py --finding F-xxx`) sin leer nada más.
