# Infraestructura

Dos servidores, mismo código, ambos leen y escriben en la **misma MariaDB (en el primario)**. Los datos de acceso (destinos SSH, rutas, qué puede hacer cada cuenta) son privados: `.claude/servers.local.md` (ignorado por git; plantilla `.claude/servers.example.md`). El runbook de producción (comandos, logs, comprobaciones de salud) está en el agente `booking-api-ops` (`.claude/agents/booking-api-ops.md`).

| | Primario `booking-api.es` | Secundario `booking-api.ddns.net` |
|---|---|---|
| Rol | API principal + la base de datos | Respaldo cuando el primario está caído o una reserva devuelve 500; el frontend envía entonces un informe a `POST /api/v1/report/fallback` |
| Stack | Docker Compose prod: `web` (`booking-flask`, Apache + mod_wsgi, termina SSL), `database` (`mariadb:10.5.19`), `worker` + `beat` (`booking-base`, Celery), `redis` (`redis:7.2.4-bookworm`), `backup`, `autoheal` | Docker; `flask run --port 5001` (Werkzeug), su propio worker/beat de Celery y su propio Redis, BD = puerto publicado del primario |
| Rama desplegada | `master` | `develop` |

**Una rama por servidor (a propósito):** el primario ejecuta siempre `master`; el secundario, siempre `develop`. Los cambios llegan al secundario por `develop` y al primario por `master`, así que mantén ambas ramas alineadas (merge de `master` a `develop` tras los hotfixes, de `develop` a `master` en las releases) y vuelve a desplegar el secundario tras cada alineación. El secundario puede ir por detrás de `master`: compruébalo antes de asumir paridad.

El secundario es un servidor personal del dueño con servicios confidenciales ajenos al proyecto: trátalo con mínimo privilegio.

## Primario (producción)
- Proyecto Compose `docker` (carpeta `docker/`), ficheros `docker/docker-compose.prod.yml`, ejecutados desde la raíz del repo con `--env-file ./docker/.env`. Contenedores `docker-web-1`, `docker-worker-1`, etc. Solo está instalado Compose v2 (`docker compose`).
- El código está montado por bind como `/app` en todos los contenedores, así que `git pull` cambia los ficheros en vivo pero los procesos siguen con el código antiguo: reinicia lo que haya cambiado. Reconstruye las imágenes (`./build.sh`) solo cuando cambien `Dockerfile.*` o `requirements.txt`.
- Puertos publicados: web 443, MariaDB 3307 (lo necesita el secundario). Redis no se publica.
- Redis es el broker/result backend de Celery y el almacén del lock de reservas: corre con AOF + `--maxmemory-policy noeviction`, contraseña y un volumen con nombre (`redis-data`). No debe perder ni expulsar datos.
- El servicio de BD de prod corre con binlogs activados para recuperación a un punto en el tiempo (ver `docs/db-backups.md`).

## Secundario
- Docker allí es el paquete snap (el socket `/var/run/docker.sock` es `root:docker`; el snap asigna ese grupo cada vez que arranca `dockerd`, así que no debería hacer falta ningún `chgrp` manual; si alguna vez aparece `root root`, ejecuta `sudo snap disable docker && sudo snap enable docker`, que reinicia todos los contenedores de ese host).
- Arranca el stack con el fichero de entorno propio del secundario, **no** con `docker/.env` (ese es la config de prod: Apache/SSL, puerto 442, y deja el contenedor web en bucle de caídas): `docker compose --env-file ./docker/.env2 -f ./docker/docker-compose.yml up -d` (`PORT=5001`, `FLASK_ENV=development`, `REDIS_PORT=6378`, más `REDIS_PASSWORD`, que también debe estar en `.env` y dentro de `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND`).
- El tráfico público llega por el 443 (un proxy frontal); el puerto 5001 no es accesible desde fuera.
- Otros proyectos ajenos comparten ese daemon de Docker: toca solo contenedores llamados `docker-*`; nunca reinicies el snap ni otros proyectos compose.
- Tiene su **propio** Redis, así que el lock de reservas no abarca ambos servidores; solo lo hace la comprobación de solapes en BD (registrado en el backlog).

### Acceso Docker restringido para el desarrollador del proyecto (secundario)
La cuenta del desarrollador no tiene grupo `docker` ni sudo general. Ejecuta `sudo booking-docker <acción>`, un wrapper propiedad de root (`/usr/local/bin/booking-docker`, permitido por `/etc/sudoers.d/booking-docker`) que solo acepta `ps` (lista los contenedores `docker-*` de este proyecto), `logs <contenedor> [1-2000 líneas]` y `restart <contenedor>` (solo `docker-web-1`, `docker-worker-1`, `docker-beat-1`). Todo lo demás se rechaza; los nombres de contenedor son una lista cerrada. **Estos dos ficheros viven solo en el secundario y no están en el repo a propósito**; si cambian los nombres de contenedor o la ruta del proyecto, edita el wrapper allí con `sudo`.

## Endpoint de salud
`GET /health` devuelve solo `{"status": ...}` (siempre HTTP 200): `ok` (base de datos, Redis y un worker de Celery responden), `degraded` (worker caído: las reservas funcionan, los emails se retrasan), `error` (Redis caído: no hay reservas) o `critical` (base de datos caída); gana el peor fallo (`helpers/HealthController.py`; el ping al worker se cachea `HEALTH_CACHE_SECONDS`=10 s, timeout `HEALTH_WORKER_TIMEOUT`=1 s). `GET /version` devuelve `VERSION` de `globals.py`.

## Ficheros Compose
`docker/docker-compose.yml` (dev, lo usa también el secundario), `docker/docker-compose.prod.yml`, `docker/docker-compose.test.yml` (nivel de tests con servicios reales). Construye las imágenes con `./build.sh` o `./build.ps1`.
