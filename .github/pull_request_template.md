## Qué y por qué
<!-- Un párrafo en español. El título de la PR va en inglés (Conventional Commits). -->

Closes #<!-- número de la issue. Una PR = una issue. Usa "Refs #n" si solo la resuelve en parte. -->

## Cómo se ha probado
<!-- Pega la salida real de lo que has ejecutado (python -m pytest tests/ ...). Di si no has pasado el nivel de servicios y por qué. -->

## Impacto en el despliegue
- [ ] Hay que reiniciar (web / worker / beat)
- [ ] Migración / cambio de esquema
- [ ] Reconstruir imagen (Dockerfile / requirements)
- [ ] Variables de entorno nuevas o cambiadas
- [ ] `VERSION` subida en `globals.py` (anterior -> nueva): 
- [ ] Ninguno

## Lista de comprobación
- [ ] La rama es `feature/*`, `fix/*` o `hotfix/*` y apunta a `develop` (hotfix: `master`)
- [ ] Incluye test de regresión (fixes) / tests nuevos (features)
- [ ] Sin secretos, `.env`, volcados ni ficheros de `private/` o `public/`
- [ ] Documentación actualizada si cambia el comportamiento o la operación
