# Configuración del tablero Project (GitHub Projects v2)

La API puede crear el proyecto, enlazarlo con el repo y añadir campos personalizados, pero **no** editar las opciones integradas de Status ni activar los workflows integrados. Eso lleva 2 minutos en la interfaz web.

## 1. Scope del token (una vez, interactivo)
```
gh auth refresh -h github.com -s project
```

## 2. Crear y enlazar (script)
```
python .claude/skills/backlog/scripts/setup_repo.py project --apply
```
Crea el proyecto de usuario "Booking API", lo enlaza con el repositorio, añade un campo `Size` (XS/S/M/L/XL) y escribe el número de proyecto en `config.json` (haz commit de ese fichero).

## 3. Pasos en la interfaz (Project → ⋯ → Settings)
1. Campo **Status**: opciones `Backlog`, `Ready`, `In progress`, `In review`, `Done`.
2. **Workflows** (⋯ → Workflows), activa:
   - *Item added to project* → Status = Backlog
   - *Item closed* → Status = Done
   - *Pull request merged* → Status = Done
   - *Auto-add to project* → filtro `is:issue,pr repo:daniieelgs/booking_api` (para que los issues creados desde la interfaz acaben en el tablero)
3. **Vistas**: tablero (Board) agrupado por Status; tabla (Table) "Triage" filtrada por `no:label` o sin prioridad; Roadmap por hito.
4. Hazlo visible para el equipo: Settings → Manage access.

## Notas
- Prioridad y Área son **etiquetas** (filtrables en cualquier vista con `label:P1`), no campos personalizados, de modo que funcionan también en listas de issues, búsquedas y la CLI.
- Los hitos son releases (`vX.Y.Z`); crea uno con `gh api repos/daniieelgs/booking_api/milestones -f title=v1.2.0 -f description="..."`.
