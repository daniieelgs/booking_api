# Estándares de issues

## Prioridad
- **P0**: producción caída, reservas fallando, pérdida de datos o una fuga de seguridad activa. Flujo de hotfix; necesita al dueño ya.
- **P1**: riesgo visible para el cliente o una garantía que prometemos (p. ej. que cada reserva reciba su email) en peligro; hacer a continuación.
- **P2**: trabajo planificado normal.
- **P3**: deseable / limpieza; hacer cuando haya tiempo libre.

## Tipo
- **bug**: el comportamiento difiere del documentado/esperado. Necesita reproducción o evidencia (id del test que falla, petición, log censurado).
- **feature**: capacidad nueva con valor de negocio. Necesita criterios de aceptación.
- **task**: trabajo operativo/de infraestructura/refactor/mantenimiento sin comportamiento nuevo de cara al usuario. Necesita una lista de comprobación y una definition of done.
- `docs` y `security` son etiquetas adicionales que se combinan con un tipo (p. ej. `task` + `security`).

## Título
Específico y fácil de buscar. Bug: el síntoma ("Closed-day check lets a worker read another local's data"). Feature/task: el resultado ("Back up the database nightly with binlog PITR"). Sin prefijos "fix:" (los commits y PRs usan Conventional Commits, los issues no). Los títulos van en inglés (convención de idioma de `CLAUDE.md`).

## Lista de comprobación de un buen cuerpo
- [ ] Por qué importa (a quién afecta, impacto de negocio o técnico)
- [ ] Evidencia o estado actual (ids de tests, `file:line`, logs censurados)
- [ ] Alcance: qué entra y qué queda explícitamente fuera
- [ ] Criterios de aceptación / definition of done verificables (incluido el test de regresión en los bugs)
- [ ] Impacto del despliegue: reinicio, migración, reconstrucción, variables de entorno, aprobación del dueño, ventana de mantenimiento
- [ ] Enlaces: `Part of #n`, `Blocked by #n`, hallazgos relacionados (`F-012`)

## Tamaño (campo del tablero)
XS < 1 h, S media jornada, M 1-2 días, L aproximadamente una semana, XL debe dividirse.

## Hace falta discusión
Si falta una decisión (diseño, modelo de datos, regla de negocio, convención transversal), añade `needs-discussion`, escribe la pregunta y las opciones en el issue, y no empieces a programar hasta que se responda.

## Cierre
Los issues se cierran mediante el PR (`Closes #n`). Cerrar sin PR (won't fix, duplicado, obsoleto) necesita un comentario con el motivo y la etiqueta `wontfix`/`duplicate`.
