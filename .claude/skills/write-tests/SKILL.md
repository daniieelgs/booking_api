---
name: write-tests
description: Crea tests nuevos para este proyecto (Flask + Celery + Redis + MariaDB) con las convenciones que se usaron al montar la suite: unitarios, integración con SQLite, servicios reales en Docker (MariaDB, Redis, worker de Celery, reinicios y caídas) y backup. Úsala siempre que el usuario pida añadir, ampliar o arreglar tests, "cubrir" una función o un endpoint con tests, comprobar que algo no se rompe, tests de resiliencia/concurrencia, o tests para un bug o una funcionalidad nueva, aunque no diga el nivel. Regla central: nunca se usa xfail ni expectedFailure; si un test falla porque el código tiene un bug, se deja en rojo y se informa.
---

# Escribir tests del proyecto

Objetivo: que cada cambio (y un despliegue automático nocturno) no pueda romper el backend sin que un test se ponga rojo.
Esta skill recoge cómo se montó la suite actual; síguela para que los tests nuevos encajen con los existentes.

## Regla innegociable: un test que falla se queda en rojo

**Prohibido** `pytest.mark.xfail`, `pytest.xfail()`, `@unittest.expectedFailure` y cualquier variante que convierta un fallo en
"esperado". Tampoco se debilita una aserción, se salta el test (`skip`) ni se borra para que pase.

Por qué: el usuario quiere ver en rojo lo que está roto para arreglarlo uno a uno; un `xfail` esconde el bug tras una suite verde
(el CI de `master` seguiría pasando) y hace que nadie lo vuelva a mirar. Un test rojo es información.

Qué hacer cuando un test nuevo falla:
1. Investiga primero si el fallo es del **test** (expectativa equivocada, dato inválido, orden, estado compartido) o del **código**.
2. Si es del test, arréglalo.
3. Si el test es correcto y el código está mal, **deja el test fallando**, no toques el código de la aplicación salvo que el usuario lo pida, y cuéntalo en el resumen final (qué test, qué bug, dónde). Para un análisis a fondo y un reporte, usa la skill `test-bug-report`.

El script `scripts/check_tests.py` lo vigila (falla si encuentra xfail/expectedFailure); ejecútalo siempre antes de terminar.

## Flujo de trabajo

1. **Entiende qué hay que cubrir y elige el nivel** (tabla abajo). Lee el código a probar entero, incluidos quien lo llama y los modelos/schemas que toca, y busca tests existentes de esa zona (`Grep` en `tests/`) para no duplicar y copiar su estilo.
2. **Lee la receta del nivel** en `references/tiers.md` (plantillas listas para copiar) y, si vas a tocar entorno, Docker o Windows, `references/lessons.md`.
3. **Escribe tests pequeños e independientes**: un comportamiento por test, nombre que dice qué pasa (`test_expired_closing_days_are_deleted`), preparar/actuar/comprobar, sin estado compartido entre tests y limpieza siempre (`addCleanup`, `finally`, `tearDown`). No amplíes los tests gigantes existentes (`test_integration_X`): se dejan como están y lo nuevo va en tests nuevos.
4. **Cubre lo que importa, no solo el camino feliz**: errores y bordes (vacío, `None`, límites, duplicados), permisos (otro local, sin token, token de rol equivocado), el estado resultante (BD, Redis, ficheros) y no solo el código HTTP, y los fallos de las dependencias (SMTP, Redis, BD caídos).
5. **Ejecuta solo lo nuevo** y mira el resultado (comandos en `references/tiers.md`). Un test que pasa a la primera no prueba que detecte nada: para lógica importante comprueba que **detecta la rotura**: rompe el código a propósito (una línea), confirma que el test se pone rojo y revierte (`git checkout <archivo>` o deshaciendo el cambio; mira `git diff` antes de seguir).
6. **Ejecuta el guardián** `python .claude/skills/write-tests/scripts/check_tests.py` (los errores son innegociables; de los avisos solo importan los de tus archivos: los `test_integration_*` antiguos salen como "sin aserciones" porque pasan `self.assertEqual` como callback, es un falso positivo conocido) y, después, la carpeta completa del nivel por si hay interferencias (no dos pytest a la vez).
7. **Resume al usuario**: qué cubre cada archivo, cuántos tests, resultado, y **qué tests están en rojo y por qué (bugs)**. Si cambia el diseño de tests (carpeta, marcador, helper), actualiza `CLAUDE.md` (sección Tests) y el README de `tests/integration/services/` si aplica.

## Qué nivel elegir

| Lo que quieres probar | Nivel | Carpeta |
|---|---|---|
| Función o clase de `helpers/` con lógica pura, cálculo, validación, schemas, seguridad, formato | Unitario | `tests/unit/` |
| Lo anterior pero necesita `db.session` o crear JWT | Unitario con BD en memoria (`DbTestCase`) | `tests/unit/` |
| Un endpoint completo por HTTP: permisos, validación, respuesta, efecto en BD (SQLite, Redis y email simulados) | Integración | `tests/integration/` |
| Cómo se comporta con **MariaDB 10.5.19, Redis 7.2.4 o Celery reales**: lock con concurrencia, versiones, esquema `db/init.sql`, tareas en un worker, reinicios y caídas, `/health` real | Servicios | `tests/integration/services/` (marcador `services`) |
| El sistema de backups de `dbbackup/` | Backup | `tests/backup/` (solo biblioteca estándar) |

Si dudas entre unitario e integración: la lógica pura va en unitario (rápida, localiza el fallo); un endpoint solo en integración. Si solo se puede observar con servicios reales, servicios. Los de servicios cuestan Docker y minutos: úsalos solo para lo que no se puede comprobar de otra forma.

## Reglas de calidad que se aprendieron por el camino

- **Aserciones sobre el resultado, no sobre la implementación**: comprueba lo que el usuario del código observa. Un mock solo para aislar dependencias externas (SMTP, reloj, red), no para espejar el código.
- **Nada de `sleep` fijos** para esperar: usa un `wait_until` con tiempo máximo (hay uno en `resilience_support.py`). Congela el reloj parcheando `now`.
- **Sin red ni SMTP reales**; sin tocar producción, la secundaria ni `docker/.env*`. Las credenciales de test son ficticias.
- **Datos únicos y limpieza garantizada**: claves de Redis con `uuid`, locales de prueba borrados al final, servicios parados vueltos a levantar en `finally`.
- **Un test no depende de otro** ni del orden. Si necesita un recurso caro, fixture con el `scope` justo.
- **Concurrencia**: `threading.Barrier` para que los hilos arranquen a la vez, y devuelve las excepciones como valores para contarlas.
- **Respeta el formato de los archivos existentes** al editarlos: muchos usan CRLF y `requirements.txt` es UTF-16; no los reescribas con un editor que lo cambie (ver `references/lessons.md`).
- **Nombres y comentarios de los tests en inglés** (como el resto de la suite); las explicaciones al usuario, en su idioma.
