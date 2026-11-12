---
name: test-bug-report
description: Ejecuta toda la suite de tests del proyecto (unitarios, integración, servicios reales en Docker y backup), analiza a fondo cada fallo (qué falla, dónde, por qué y cómo arreglarlo, más otros hallazgos del código) y deja el análisis en JSON en private/reports/tests/ junto con un reporte HTML; después, cuando se arreglan los bugs, re-ejecuta solo los tests afectados y actualiza JSON y HTML. Úsala siempre que el usuario pida un informe/reporte de tests o de bugs, "ejecuta todos los tests y analiza los fallos", "qué falla en la suite", "actualiza el reporte", "vuelve a probar lo que arreglé", o cuando un agente vaya a arreglar bugs detectados por los tests y necesite el contexto sin volver a correr nada. También cuando se mencione private/reports/tests, findings.json o results.json.
---

# Reporte de tests y bugs

Convierte la ejecución de la suite en conocimiento reutilizable: un análisis por bug guardado en JSON que cualquier
agente (o persona) puede leer sin volver a ejecutar los tests ni leer el HTML, y un HTML que lo muestra.

Todo vive en `private/reports/tests/` (ignorado por git):

- `results.json` — números y resultado de cada test. Lo escriben los scripts.
- `findings.json` — el análisis (qué, dónde, por qué, arreglo). Lo escribes tú. Formato exacto en `references/schema.md`: léelo antes de escribir hallazgos.
- `report.html` — vista generada a partir de los dos JSON.

Los scripts están en `.claude/skills/test-bug-report/scripts/`. Ejecútalos con el python del entorno virtual del proyecto
(`.venv`, el que tiene pytest y las dependencias); desde la raíz del repo. Si el usuario no tiene el venv activo,
usa `.venv/Scripts/python.exe` (Windows) o `.venv/bin/python`.

## Elige el modo según lo que pida el usuario

| Quiere… | Haz |
|---|---|
| Informe completo / "ejecuta todo y analiza" | **Modo A** |
| Arreglar bugs (él o un agente) y saber qué hay que hacer | **Modo C**: lee solo `findings.json` |
| Comprobar que lo arreglado funciona / actualizar el reporte | **Modo B** |
| Ver el reporte | `build_report.py` si los JSON han cambiado y abrir `report.html` |

## Modo A — ejecutar todo y analizar

1. **Ejecuta la suite completa** (en segundo plano: tarda 3–4 min; los niveles se ejecutan uno tras otro, nunca en paralelo porque comparten el SQLite de test y los contenedores):

   ```bash
   python .claude/skills/test-bug-report/scripts/run_tests.py
   ```

   Hace los cuatro niveles. El de servicios levanta él mismo `docker/docker-compose.test.yml` y lo elimina al terminar; si
   Docker no responde, lo marca `not_run`, conserva los números anteriores como `stale` y lo dice en la salida. **No inventes ese dato**: cuéntaselo al usuario, que puede arrancar Docker Desktop y repetir con `--tiers services`.
   Al acabar escribe `results.json`, actualiza el estado de los hallazgos que ya existían, genera el HTML y lista los
   **fallos sin analizar** (los que no están en `findings.json`).

2. **Analiza cada fallo sin analizar a fondo.** Es la parte que no se puede automatizar y la que da valor: sin ella el reporte es solo una lista de tests rojos. Por cada fallo:
   - Lee la entrada de `failures` en `results.json` (mensaje, `crash_path:crash_line`, traza) y el **test completo**: entiende qué escenario monta y qué espera.
   - Lee el **código de la aplicación** al que apunta la traza y los alrededores (llamadores, modelos, schemas). Comprueba las líneas con Read en el estado actual: no cites líneas de memoria.
   - Decide si el fallo es un **bug del código** o un **defecto del test** (expectativa errónea, dato inválido, test frágil). Si es del test, arréglalo y no lo registres como bug; si el test es correcto, es un bug.
   - Si la causa no es evidente, **reprodúcela**: un script corto o un experimento con el propio test te da evidencia real (guarda el resultado en `evidence` con `type: "experiment"`). Una hipótesis sin comprobar no es una causa raíz.
   - Agrupa: varios tests que fallan por el mismo defecto son **un** hallazgo con varios `tests`.
   - Escribe el hallazgo siguiendo `references/schema.md`: qué hace el test, qué falla, **por qué** (línea o razonamiento exacto), archivos y líneas, arreglo concreto (con fragmento de código si ayuda) y tamaño del cambio.
   - Tamaño `discuss` cuando el arreglo afecta al diseño, la arquitectura, el modelo de datos o una convención transversal (p. ej. cómo se guardan las fechas y zonas horarias, una tarea periódica nueva, cambios de esquema), o cuando falta una decisión de negocio. En `discuss_reason` explica qué hay que decidir y por qué. Así el usuario sabe qué comentar antes de que nadie toque código.
   - Severidad por impacto real: fuga de datos entre locales, pérdida de reservas o de correos = alta/crítica; un cálculo que falla solo en un borde raro = baja/media.

3. **Busca otros hallazgos** (`kind: "extra"`): mientras lees el código afectado, anota lo que veas aunque ningún test lo cubra (patrones repetidos en otros recursos, secretos en logs, imports erróneos, riesgos de pérdida de datos). Pregúntate si el mismo defecto existe en código parecido: un bug de propietario en un endpoint suele estar en sus hermanos. Cada uno con el mismo rigor: dónde, por qué, arreglo. Si dudas de que sea un bug real, dilo en la descripción en vez de afirmarlo.

4. **Guarda y genera**: escribe `findings.json` (añade con `findings.py add fichero.json` o edita el JSON respetando el esquema y conservando los hallazgos y el `history` existentes; no renumeres ids) y ejecuta:

   ```bash
   python .claude/skills/test-bug-report/scripts/build_report.py
   ```

5. **Cuenta al usuario** el resumen (ejecutados, pasan y fallan con %), los bugs más graves, los marcados `discuss` y la ruta de `report.html`. Escribe los hallazgos en el idioma del usuario.

## Modo B — tras arreglar bugs

No repitas toda la suite: solo los tests de los hallazgos afectados.

```bash
python .claude/skills/test-bug-report/scripts/recheck.py --finding F-003 F-004     # o --open, o --tests <nodeid>
```

Re-ejecuta únicamente esos tests, actualiza los resultados y marca como `fixed` los hallazgos cuyos tests pasan (o los
mantiene/reabre como `open`, con el último fallo adjunto). Regenera el HTML. Después:

- Los hallazgos `extra` no tienen tests: cuando se arreglen, `findings.py status F-012 fixed --note "..."` (y comprueba el código tú).
- Si un hallazgo sigue `open`, mira `latest_failure`: ¿arreglo incompleto o la causa raíz era otra? Corrige el hallazgo si tu análisis estaba equivocado.
- Si pytest no encuentra un test (renombrado o borrado), actualiza `tests` en el hallazgo.
- Si el arreglo ha tocado código compartido, avisa de que `recheck` solo comprueba los tests indicados y sugiere una pasada completa (`run_tests.py`) antes de dar el trabajo por cerrado.

## Modo C — arreglar bugs sin volver a ejecutar nada

El contexto ya está en el JSON. No abras el HTML ni ejecutes la suite:

```bash
python .claude/skills/test-bug-report/scripts/findings.py list --status open       # qué hay (filtros: --tier, --size)
python .claude/skills/test-bug-report/scripts/findings.py show F-003               # el hallazgo completo
```

`show` da los tests, la causa raíz, la evidencia, los archivos con líneas y el arreglo sugerido. Los hallazgos con
`change_size: "discuss"` **no se arreglan sin hablar antes con el usuario**: léele `discuss_reason` y pregúntale. Tras
el arreglo, Modo B. Las líneas del JSON son de cuando se hizo el análisis: compruébalas antes de editar si el código ha cambiado.

## Por qué está hecho así

- Los scripts hacen lo determinista (ejecutar, medir, contar, sincronizar estados) para que los números nunca dependan de la memoria ni de la interpretación del modelo.
- El análisis lo haces tú, leyendo código de verdad, porque un mensaje de aserción rara vez explica la causa.
- El JSON separa datos de vista: el HTML carga los JSON (en vivo si se sirve por http; con una copia embebida si se abre con doble clic, porque los navegadores bloquean `fetch` sobre `file://`) y un agente nunca necesita leerlo.
- Los tests de servicios cuestan Docker y minutos; por eso el re-chequeo ejecuta solo los afectados.

## Reglas del proyecto que importan aquí

- Los tests que fallan por un bug real **no llevan `xfail`**: el usuario quiere verlos en rojo hasta que se arreglen.
- No ejecutes dos pytest a la vez (SQLite de test compartido) ni mezcles `tests/integration/services` con otros niveles en un mismo comando (`globals.py` fija el entorno al importarse): los scripts ya lo respetan.
- No toques producción ni los servidores; todo es local. `private/` nunca se sube a git.
