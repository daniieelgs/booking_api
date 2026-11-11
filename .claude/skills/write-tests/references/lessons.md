# Lecciones y trampas de esta base de código

Lee esto antes de tocar entorno, Docker, formatos de archivo o Windows. Cada punto costó tiempo al montar la suite.

## Entorno y configuración

- **`globals.py` fija el entorno al importarse** y llama a `load_dotenv(override=True)`: un `.env` local puede pisar el entorno de los tests. Por eso `conftest.py` raíz pone `FLASK_DEBUG=1` antes de importar, y el `conftest.py` de servicios aborta si no apunta a los puertos de test. No importes `globals` antes de que se aplique el entorno.
- `is_redis_test_mode()` / `is_email_test_mode()` solo se respetan con `DEBUG` activo. Si un test "no usa el modo test", mira primero `DEBUG`.
- **Los tests de servicios van solos** en su comando (no mezclados con unit/integration) y **nunca dos pytest a la vez** (SQLite `instance/data_test.db` compartido, contenedores compartidos).
- Los nombres se parchean **en el módulo que los usa**: `from helpers.Database import ping_redis` en `resources/status.py` se parchea como `resources.status.ping_redis`. Y un módulo que hace `import redis` comparte el objeto `redis` global: parchear `Database.redis.ConnectionPool` parchea también el de los demás (guarda la clase real en una constante antes de parchear si la necesitas).
- `tests/__init__.py` debe estar **vacío**: si importa la app, los tests de backup (stdlib puro) dejan de ser independientes.

## Formatos de archivo

- **`requirements.txt` es UTF-16-LE con BOM y CRLF**. Edítalo con Python (`open(..., encoding='utf-16')`, conservando CRLF y BOM), nunca con un editor que asuma UTF-8: se corrompe. Para el CI, `pip install -r` lo lee bien.
- Muchos `.py` del repo usan **CRLF** (`app.py`, `globals.py`, `schema.py`, `CLAUDE.md`...). Al editar con Python abre con `newline=''` y reutiliza el salto de línea del archivo (`'\r\n' if '\r\n' in s else '\n'`). Los `.sh` deben ser **LF** (`.gitattributes` lo fuerza): CRLF los rompe en Linux.
- En Python, una ruta de Windows como `.\scripts\run...` dentro de una cadena normal convierte `\r` en retorno de carro: escapa la barra o usa cadena raw.

## Windows y la terminal

- La herramienta Bash es Git Bash. Un bloque `cat > archivo <<'EOF'` con comillas/apóstrofos complicadas puede fallar al interpretarse y **no escribir nada**: para crear archivos usa la herramienta de escritura de archivos, no heredocs.
- PowerShell no admite `VAR=1 comando`: `$env:RUN_INTEGRATION_TESTS = "1"` y quitarla después (`Remove-Item Env:RUN_INTEGRATION_TESTS`). Los scripts `scripts/run_services_tests.*` ya lo hacen.
- Docker Desktop tarda en arrancar y a veces el motor responde 500 un buen rato; comprueba con `docker info`. Si no responde, di al usuario que no has podido ejecutar el nivel de servicios en vez de darlo por bueno.

## Patrones que dieron problemas

- **Mutar una lista mientras se recorre** (bug real en `getClosedDays`): si un test de "borra todos" falla alternando, mira eso.
- **`datetime` sin zona + pytz**: no se pone `tzinfo` con `replace()`, se usa `localize()`. Los cambios de hora (último domingo de marzo/octubre) son un borde que merece su test.
- **`except:` sin tipo** que devuelve `False` esconde la causa (bug real en `render_page`); si un test espera un error pero el código lo traga, comprueba el valor devuelto y los logs.
- `generateTokens` decodifica el token que acaba de crear, así que no se puede fabricar uno ya caducado con esa función: fabrícalo con `jwt.encode` y `exp` en el pasado.
- Para esperar a un proceso (worker de Celery) lee su log buscando `ready.`, con tiempo máximo; si no llega, falla mostrando el final del log.
- Un test de "tarda ~1 s" (timeouts reales) está bien si es pocos; si hay muchos, parchea `time.sleep`.
- Cuidado con tests que **pasan por accidente**: un mock mal puesto que provoca un `RecursionError` capturado por un `except Exception` del código pasa y no prueba nada. Exige la excepción concreta con `assertRaises` en el paso previo y comprueba el efecto real.
- Los reintentos automáticos (`pytest-rerunfailures`) enmascaran tests inestables: solo con causa documentada y como parche temporal; lo correcto es arreglar la causa (hay un `test_email.py` pendiente de dividir por eso).

## Verificar que un test detecta la rotura

Para lógica importante, rompe el código una línea (por ejemplo desactivar `WATCH`, quitar una comparación de propietario o invertir un `<`), ejecuta el test, confirma que sale **rojo** y revierte
inmediatamente (`git checkout <archivo>` si no tenía cambios tuyos sin guardar; si los tenía, deshaz a mano). Comprueba con `git diff` que no queda nada. Un test que sigue verde con el código roto no vale.

## Cuando aparece un bug real

Se queda el test en rojo, sin `xfail`. Anota qué test falla, qué hace mal el código, en qué archivo y línea y una idea de arreglo, y dilo en el resumen. Si hay varios, la skill `test-bug-report` los analiza a fondo y los guarda en `private/reports/tests/`.
