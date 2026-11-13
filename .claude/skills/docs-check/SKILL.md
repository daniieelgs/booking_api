---
name: docs-check
description: Ejecuta el comprobador de consistencia de la documentación - verifica que existen las rutas del repo mencionadas en CLAUDE.md, docs/, agentes y skills, que los enlaces relativos se resuelven, que CLAUDE.md respeta su presupuesto de tamaño y no tiene roadmap, y que los agentes/skills tienen un frontmatter válido. Úsala antes y después de editar documentación, en PRs que toquen docs/agentes/skills, y cuando pregunten "está la documentación al día" o "revisa los docs".
---

# docs-check

```bash
python .claude/skills/docs-check/scripts/check_docs.py          # report; exit 1 if there are errors
python .claude/skills/docs-check/scripts/check_docs.py --strict # warnings also fail
```

Ejecútalo desde la raíz del repo. Comprobaciones (todas de solo lectura):

| Comprobación | Nivel |
|---|---|
| `CLAUDE.md` supera el presupuesto de tamaño (18 000 bytes) | error |
| `CLAUDE.md` tiene una sección "Roadmap"/"pending tasks" (pertenece al backlog de GitHub) | error |
| Rutas del repo entre comillas invertidas en los docs (por ejemplo `resources/<file>.py` o `docs/<file>.md`, `.claude/...`, `scripts/...`) que no existen | error |
| Enlaces relativos de Markdown que no se resuelven | error |
| Fichero de agente/skill sin frontmatter `name`/`description`, o con un nombre distinto de su carpeta/fichero | error |
| Comandos `python ...scripts/*.py` mencionados cuyo script no existe | error |
| Los docs mencionan números de `VERSION` distintos de los de `globals.py` | warning |

El comprobador encuentra **solo referencias rotas**; no puede saber si una frase sigue siendo cierta. Cuando pasa, contrasta por muestreo las afirmaciones con el código (variables de entorno, nombres de contenedores, comandos, comportamiento), que es lo que hace el agente `docs-keeper`.

Las rutas que legítimamente no existen en el repo (ignoradas por git o solo del servidor) están listadas en `IGNORED` dentro del script: `private/`, `public/`, `.env*`, `.claude/servers.local.md`, `migrations/`, `instance/`, `.venv/`.
