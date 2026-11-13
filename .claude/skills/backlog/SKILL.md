---
name: backlog
description: Gestiona el backlog del proyecto en GitHub (issues, etiquetas, hitos, tablero Project). Úsala para crear bugs/funcionalidades/tareas bien especificados, triar y priorizar, auditar la calidad del backlog, enlazar el trabajo con los PRs para que al fusionar se cierre el issue, planificar una release (hito) o configurar las etiquetas/el tablero del repo. Se activa con "crea un issue", "añade esto al backlog", "qué hay pendiente", "prioriza", "planifica la próxima release", "triaje", "enlaza el PR con el issue", "configura el tablero del proyecto", y siempre que otra skill o agente encuentre un bug o tarea que deba registrarse.
---

# Backlog (GitHub como única fuente de verdad del trabajo pendiente)

El trabajo pendiente vive en **GitHub Issues + el tablero Project**, no en `CLAUDE.md`. Todo se maneja con la CLI `gh`.
La configuración (repo, número de proyecto) está en `.claude/skills/backlog/config.json`. El repositorio es **público**: ver "Reglas del repo público".

## Cómo encajan las piezas

| Pieza | Propósito | Dónde |
|---|---|---|
| **Issue** | Una unidad de trabajo, totalmente especificada (bug / feature / task) | formularios de issue en `.github/ISSUE_TEMPLATE/` |
| **Etiquetas** | Tipo (`bug` `feature` `task` `docs` `security`), prioridad (`P0`-`P3`), área (`area:*`), indicadores (`needs-discussion` `blocked` `production` `from-test-report`) | `references/labels.json` |
| **Hito (milestone)** | Una release (`v1.2.0`): el conjunto de issues que salen juntos; coincide con `VERSION` en `globals.py` | milestones de GitHub |
| **Tablero Project** | Estado del flujo: Backlog → Ready → In progress → In review → Done; más Size | ver `references/project-setup.md` |
| **PR** | Implementa exactamente un issue; el cuerpo lleva `Closes #n` | `.github/pull_request_template.md` |

Regla general: las etiquetas dicen **qué** es, el hito dice **cuándo sale**, el tablero dice **dónde está ahora**.

## Ciclo de vida

1. **Crear** (`scripts/issue.py create`, o el formulario web). Debe tener tipo, prioridad, área y las secciones obligatorias (abajo).
2. **Triaje**: un mantenedor comprueba que está bien definido, fija prioridad/área, añade `needs-discussion` si falta una decisión y lo mueve a *Ready* cuando alguien podría empezar sin hacer preguntas.
3. **Trabajo**: rama `fix/<name>` o `feature/<name>` desde `develop`, con el nombre tomado del issue; muévelo a *In progress*. Un issue = una rama = un PR. Para un conjunto de issues relacionados usa una rama paraguas (ver GitFlow en CLAUDE.md); el PR paraguas lista cada `Closes #n`.
4. **PR** hacia `develop` con `Closes #n`. GitHub solo cierra automáticamente al fusionar en la rama por defecto (`master`), así que `.github/workflows/close-linked-issues.yml` cierra los issues cuando el PR se fusiona en `develop`. Usa `Refs #n` para trabajo parcial.
5. **Release**: PR `develop` → `master` con los issues del hito listados; el hito se cierra tras el despliegue.

## Crear un issue bien definido

Idioma (ver `CLAUDE.md`): título en inglés; texto del cuerpo en español; mantén en inglés los encabezados `### ` de abajo porque `issue.py` los valida.

Ejecuta desde la raíz del repo. Escribe el cuerpo en un fichero (scratchpad) y luego:

```bash
python .claude/skills/backlog/scripts/issue.py create --type bug --title "Imperative or descriptive, specific" \
  --body-file body.md --priority P1 --area email [--milestone v1.2.0] [--label needs-discussion] [--dry-run]
```

Rechaza cuerpos sin las secciones `### ` obligatorias, avisa de posibles secretos, aplica las etiquetas y añade el issue al tablero. Secciones obligatorias:

- **bug**: `Summary`, `Steps to reproduce / evidence`, `Expected vs actual behaviour` (+ recomendadas `Root cause / affected code`, `Proposed fix and how to verify`)
- **feature**: `Problem / goal`, `Proposed solution and scope`, `Acceptance criteria` (lista de comprobación `- [ ]`) (+ `Technical notes and deployment impact`)
- **task**: `Context and goal`, `Plan / checklist`, `Definition of done` (+ `Risks and approvals needed`)

Listón de calidad (ver `references/issue-standards.md`): alguien sin contexto puede empezar a trabajar sin hacer preguntas; el título nombra el síntoma o el resultado, no la solución; los criterios de aceptación / definition of done son verificables; se indican el impacto en producción y las aprobaciones del dueño. Divide todo lo que supere ~1 semana o toque varias áreas en issues enlazados (`Part of #n`, listas de tareas).

## Comandos del día a día

```bash
gh issue list --label P0 --state open               # what is urgent (repeat --label for AND)
gh issue list --search 'label:bug label:area:email'
gh issue view 12 --comments
gh issue edit 12 --add-label needs-discussion --milestone v1.2.0
gh issue comment 12 --body "..."
python .claude/skills/backlog/scripts/issue.py audit  # issues missing type/priority/area/sections
gh pr create --base develop --title "fix: ..." --body-file pr.md   # pr.md ends with "Closes #12"
```

## Configuración puntual / ocasional (idempotente)

```bash
python .claude/skills/backlog/scripts/setup_repo.py labels             # create/update the label set
python .claude/skills/backlog/scripts/setup_repo.py settings [--apply]  # delete head branch on merge, merge commits only
python .claude/skills/backlog/scripts/setup_repo.py project [--apply]   # board + Size field (needs: gh auth refresh -h github.com -s project)
```

`settings` y `project` modifican el repositorio: son simulaciones (dry run) salvo con `--apply`, y aplicarlos necesita el visto bueno del dueño.

## Reglas del repo público

El repo es público. Nunca pongas en un issue/PR: secretos, tokens, contraseñas de SMTP/BD, datos personales de clientes, logs de producción en bruto, hostnames/IPs/puertos de servidores ni pasos de explotación. Describe el trabajo de seguridad de forma genérica (p. ej. "restringir la exposición del puerto de la base de datos") y guarda los detalles sensibles en `.claude/servers.local.md` o en un canal privado. Las vulnerabilidades van por el security advisory privado de GitHub, nunca en un issue público.

## Integración con otro trabajo

- `test-bug-report` publica aquí los hallazgos confirmados (preguntando antes al usuario) y vuelve a leer los issues `bug` abiertos en `findings.json`.
- Los agentes que encuentren un bug mientras hacen otra cosa: abren un issue (o lo proponen) en lugar de arreglarlo sobre la marcha; un bug = una rama `fix/*`.
- Los agentes nunca fusionan PRs, hacen push a `master`/`develop`, cambian la configuración del repo ni cierran issues abiertos por otros sin la confirmación explícita del usuario.
