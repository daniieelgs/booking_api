---
name: release
description: Prepara y verifica una release de la Booking API - comprueba que develop está listo, redacta las notas de la release a partir de los PRs fusionados y los issues cerrados, confirma el incremento de VERSION y prepara el PR develop -> master más la lista de comprobación del despliegue (ventana de baja carga, smoke test, realineación del secundario). Úsala para "prepara una release", "qué sale", "notas de la release", "está develop listo para master", "corta la v1.2.0". Nunca fusiona ni despliega por sí sola.
---

# Release (develop → master → primario)

Las releases siguen el GitFlow de `CLAUDE.md`: los PRs de feature/fix aterrizan en `develop` (verificado en el secundario), luego **un PR `develop` → `master`**, y después el dueño despliega el primario en una ventana de baja carga. Hito = release (`vX.Y.Z`, coincide con `VERSION` en `globals.py`).

## 1. Comprobar que está lista (solo lectura)

```bash
python .claude/skills/release/scripts/release_check.py            # compares origin/develop with origin/master
python .claude/skills/release/scripts/release_check.py --notes     # also prints release notes (Markdown) for the PR body
```

Informa de: la versión en `develop` frente a `master` (debe ser mayor, SemVer), los PRs fusionados y los issues que cierran, las últimas ejecuciones de CI en `develop`, los bugs `P0`/`P1` abiertos y los issues abiertos del hito, y si `master` tiene commits que faltan en `develop` (un hotfix no fusionado de vuelta: arréglalo primero).

Detente y avisa al usuario si: la CI en `develop` está en rojo, no se incrementó la versión, hay bugs `P0` abiertos, `master` va por delante de `develop`, o el secundario aún no ejecuta `develop` / no se verificó (pregúntale al dueño; tú no puedes verlo).

## 2. Redactar el PR de release

Solo cuando el usuario esté de acuerdo. La protección de ramas exige un PR y el check `tests` en `master`.

```bash
gh pr create --base master --head develop --title "release: vX.Y.Z" --body-file notes.md
```

Cuerpo = la salida de `--notes` más: el impacto de despliegue agregado de los PRs (reinicios: web/worker/beat; migraciones; reconstrucción de imágenes; nuevas variables de entorno), **no** hace falta `Closes` (los issues ya los cierra el workflow `close-linked-issues`), y el enlace al hito.

## 3. Lista de comprobación del despliegue (la ejecuta el dueño; el runbook de producción está en el agente `booking-api-ops`)
- [ ] Ventana de baja carga, fuera del horario de apertura del salón.
- [ ] Fusionar el PR (dueño), `git pull` en el primario como `ubuntu`, reconstruir las imágenes solo si cambió `Dockerfile.*`/`requirements.txt`, reiniciar lo que cambió.
- [ ] `scripts/smoke_test.sh --url <api> --expect-version X.Y.Z --worker <container>` pasa.
- [ ] Vigilar `/health` y el log del worker durante unos minutos.
- [ ] Redesplegar el secundario (ejecuta `develop`, que ahora es igual a `master`).
- [ ] Cerrar el hito y mover los issues sobrantes al siguiente: `gh api -X PATCH repos/daniieelgs/booking_api/milestones/<n> -f state=closed`.
- [ ] Opcionalmente etiquetar: `git tag -a vX.Y.Z origin/master -m "vX.Y.Z"` y una release de GitHub a partir de las notas (preguntar antes; las etiquetas son públicas).

## Releases de hotfix
Los arreglos urgentes usan `hotfix/*` desde `master` (ver el agente `scrum-master`); incrementa la versión de parche en el PR del hotfix y luego abre `master` → `develop`.
