# Backups de la base de datos

Sistema de copias de seguridad de la MariaDB del servidor **primario**, con copia cifrada en el **secundario**.
Todo el código está en `dbbackup/` (solo librería estándar de Python), se ejecuta en su propio contenedor `backup`
y se prueba con `tests/backup/` (unitarios) y `tests/backup/e2e/run_e2e.sh` (integración con Docker).

## Qué protege y hasta dónde

| Capa | Qué es | Dónde vive | Para qué sirve | Pérdida máxima |
|---|---|---|---|---|
| **Binlog** de MariaDB | Registro continuo de cada transacción (`log_bin`, 7 días) | Primario (volumen `db-data`) | Volver a *cualquier segundo* de los últimos 7 días tras un `DELETE`/`UPDATE` accidental | ~0 (segundos) |
| **Dump diario** 04:00 | Volcado completo y consistente (`mysqldump --single-transaction`), comprimido | Primario (`backup-data`, últimos 2) | Base para reconstruir el pasado + los binlogs | — |
| **Copia en el secundario** | Dump cifrado (`age`) + binlogs cerrados, enviados por rsync/SSH | Secundario (`/home/dbbackup/incoming`, últimos 3 dumps) | Fallo grave del primario (disco, servidor) | Lo posterior al último binlog enviado (≤ 6 h) |

* Si el primario se pierde por completo: se levanta una BD en el secundario con el último dump + binlogs (`promote-secondary.sh`).
  Se pierde, como máximo, lo ocurrido desde el último binlog archivado (≤ `BACKUP_BINLOG_SHIP_HOURS`, 6 h por defecto).
* Un error pequeño (borrado accidental) se arregla **sin parar el servicio ni afectar a clientes** (`restore.sh`).
* Los binlogs **no se envían continuamente** al secundario: solo los ficheros ya cerrados, cada 6 h y justo después del dump
  (unos KB/MB al día), para no cargar el servidor secundario.
* Si el secundario está caído, las copias quedan pendientes en el primario y se **reintentan cada 15 min**; nunca se borran
  mientras no se hayan entregado (con un tope de 7 dumps sin entregar para no llenar el disco).

## Piezas

```
PRIMARIO                                                SECUNDARIO
 database  (--log-bin, ROW, 7 días)                      cuenta 'dbbackup' (solo subida, rrsync -wo)
    ▲  usuario de BD 'backup' (solo lectura)               incoming/  dump-*.sql.gz.age + .meta.json + mysql-bin.*.gz.age
    │                                                      ▲
 backup (contenedor) ── 04:00 dump ──┐                     │ rsync/SSH, cifrado con age, reintentos cada 15 min
    │  cada 6 h: FLUSH + binlogs     ├─► /backups ─────────┘
    │  heartbeat ─► Uptime Kuma      │   (volumen backup-data)        cron del secundario: prune.py (últimos 3 dumps)
 restore-db (BD temporal, solo bajo el perfil "restore")
```

### Qué usuario de base de datos se crea

`backup` (`scripts/create-backup-db-user.sh`). Es un usuario **de MariaDB**, solo de lectura:
`SELECT, SHOW VIEW, TRIGGER, EVENT, LOCK TABLES` (volcar datos), `RELOAD` (`FLUSH BINARY LOGS`), `REPLICATION CLIENT`
(`SHOW BINARY LOGS`) y `REPLICATION SLAVE` (descargar binlogs). No puede insertar, modificar ni borrar nada, y está
limitado al host `172.%` (red interna de Docker) porque el puerto 3307 está publicado.

### Qué es la "cuenta restringida" del secundario

Una cuenta **de Linux** (`dbbackup`) en el secundario, distinta de `daniieelgs` e `isma`, que solo sirve para que el
primario le suba ficheros. No tiene contraseña ni sudo ni docker, y en su `authorized_keys` la clave del primario va
con `restrict,command="rrsync -wo /home/dbbackup/incoming"`: aunque alguien robase la clave del primario, solo podría
**escribir** en ese directorio (no leer, no listar, no borrar fuera, no abrir shell, no reenviar puertos). La retención
(borrar dumps antiguos) la hace el propio secundario con su cron, así que un primario comprometido no puede borrar las
copias que ya envió.

## Puesta en marcha

Rama de trabajo: `feature/db-backups` → `develop` (probar, desplegar en el secundario) → `master` (primario).

### 1. Claves (una vez, en tu equipo)

```bash
# Clave de cifrado de las copias. La PRIVADA se guarda offline (gestor de contraseñas), NUNCA en un servidor.
age-keygen -o age_key.txt          # imprime "Public key: age1..."  -> BACKUP_AGE_RECIPIENT
# Clave SSH para que el primario suba ficheros al secundario
ssh-keygen -t ed25519 -N '' -C primary-backup -f backup_ssh_key
```

Sin la clave privada de `age` **no se puede restaurar nada del secundario**: guárdala en dos sitios.

### 2. Secundario (con la aprobación del dueño; solo toca un usuario, un directorio y un cron)

```bash
sudo useradd -m -s /bin/sh dbbackup          # /bin/sh: sshd ejecuta el comando forzado a través del shell
sudo passwd -l dbbackup                      # sin contraseña
sudo install -d -o dbbackup -g dbbackup -m 700 /home/dbbackup/.ssh
sudo install -d -o dbbackup -g dbbackup -m 750 /home/dbbackup/incoming
command -v rrsync                            # normalmente /usr/bin/rrsync (viene con el paquete rsync)
echo 'restrict,command="/usr/bin/rrsync -wo /home/dbbackup/incoming" <contenido de backup_ssh_key.pub>' \
  | sudo tee /home/dbbackup/.ssh/authorized_keys
sudo chown dbbackup:dbbackup /home/dbbackup/.ssh/authorized_keys && sudo chmod 600 /home/dbbackup/.ssh/authorized_keys

# Retención (últimos 3 dumps y los binlogs que necesitan). Copia el fichero; es solo stdlib.
sudo install -o dbbackup -g dbbackup -m 755 dbbackup/prune.py /home/dbbackup/prune.py
echo '30 5 * * * python3 /home/dbbackup/prune.py --dir /home/dbbackup/incoming --keep-dumps 3' | sudo crontab -u dbbackup -
```

Comprueba que el usuario es realmente restringido: `ssh -i backup_ssh_key dbbackup@<secundario> id` **no** debe devolver `uid=`.
No olvides volver a copiar `prune.py` si cambia.

### 3. Uptime Kuma (en el secundario)

Crea un monitor de tipo **Push**, intervalo 900 s (el servicio avisa cada 5 min) y copia su URL
(`https://.../api/push/XXXX`) en `BACKUP_KUMA_PUSH_URL`. El servicio envía `status=up` con `OK`, o `status=down` con el motivo:
sin dump reciente (>26 h), binlogs sin archivar (>18 h) o secundario inalcanzable (>24 h con copias pendientes).
Si el contenedor muere, Kuma avisa por falta de latidos.

### 4. Primario

```bash
git pull                                      # rama master, tras el merge
./build.sh                                    # construye también la imagen booking-backup
cp docker/.env.backup.example /tmp/vars       # copia las variables que falten a docker/.env (BACKUP_*)
mkdir -p docker/secrets
cp backup_ssh_key docker/secrets/backup_ssh_key
ssh-keyscan -t ed25519 <secundario> > docker/secrets/backup_known_hosts     # verifica la huella con el dueño
chmod 600 docker/secrets/*

sudo docker compose --env-file ./docker/.env -f ./docker/docker-compose.prod.yml up -d database   # <-- REINICIA la BD (segundos de corte): hacerlo de madrugada
./scripts/create-backup-db-user.sh
sudo docker compose --env-file ./docker/.env -f ./docker/docker-compose.prod.yml up -d backup
sudo docker logs --tail 30 docker-backup-1    # el primer ciclo hace un dump y lo envía sin esperar a las 04:00
```

El reinicio de `database` activa el binlog (`--log-bin=mysql-bin ...` en `docker-compose.prod.yml`). Hasta entonces no hay
restauración al instante, solo dumps. `docker-web-1` reconecta solo.

## Operación

```bash
sudo docker logs --tail 50 docker-backup-1                       # actividad del servicio
sudo docker exec docker-backup-1 cat /backups/state/status.json  # salud, pendientes, último dump/envío
sudo docker exec docker-backup-1 ls -la /backups/dumps /backups/binlogs
sudo docker ps                                                   # docker-backup-1 debe estar (healthy)
```

El healthcheck del contenedor solo comprueba que el bucle sigue vivo. Los problemas de calidad (dump viejo, secundario caído)
se notifican por Uptime Kuma, a propósito: así `autoheal` no reinicia el contenedor en bucle por algo que no arregla.

## Restaurar filas borradas por error (`scripts/restore.sh`)

No para ni toca la BD de producción. Reconstruye el pasado en una BD temporal y re-inserta **solo las filas que faltan**.

```bash
# 1. ¿Cuándo ocurrió? (lista DELETE/UPDATE con su hora)
./scripts/restore.sh --inspect --since "2026-11-07 09:00:00"
#   2026-11-07 10:32:05  DELETE  bbdd.booking          x2
#   2026-11-07 10:32:05  DELETE  bbdd.service_booking  x3

# 2. Simulacro (no cambia nada): usa una hora justo ANTES del borrado
./scripts/restore.sh --until "2026-11-07 10:32:00"
# 3. Si el resumen es el esperado, aplicarlo
./scripts/restore.sh --until "2026-11-07 10:32:00" --apply
```

* Opciones: `--tables booking,service_booking` (limitar), `--source archive` (leer binlogs de `/backups/binlogs` si el servidor
  ya los purgó, pasados 7 días), `--yes` (sin confirmación).
* Funciona porque el dump más reciente anterior a `--until` se carga en una MariaDB temporal, se reproducen los binlogs hasta esa hora y se
  comparan las claves primarias con la BD real. Los `ON DELETE CASCADE` se recuperan porque se compara **toda** la BD.
* `INSERT IGNORE`: nunca modifica ni duplica filas existentes; repetirlo es inofensivo.
* Límites conocidos: solo recupera filas **borradas** (no `UPDATE`); si entre `--until` y ahora se borró algo
  *legítimamente* (p. ej. tokens caducados), se vuelve a insertar, por eso existe el simulacro; y los *triggers*
  `before_insert_*` ponen `datetime_created`/`datetime_updated` a la hora de la restauración.
* El SQL generado queda en `/backups/restore/recovered-<fecha>.sql` por si se quiere revisar.

## Fallo grave del primario (`scripts/promote-secondary.sh`)

En el **secundario** (el repo en `/home/daniieelgs/booking/backend/booking_api`, rama `develop`):

```bash
./scripts/promote-secondary.sh --age-key /ruta/a/age_key.txt --plan-only      # qué se restauraría (no cambia nada)
./scripts/promote-secondary.sh --age-key /ruta/a/age_key.txt
```

Crea un contenedor `booking-db-promoted` (volumen propio, alias `database-promoted` en la red `docker_default`), descifra y
canaliza el dump y los binlogs contiguos directamente al `mysql` del contenedor (**sin texto claro en disco**), muestra
recuentos y **te dice los 3 pasos para apuntar la app del secundario a esa BD** (`DATABASE_HOST=database-promoted` y reiniciar
`web/worker/beat`). No modifica el `.env` ni los contenedores existentes: cambiar de BD es una decisión tuya.

* Necesita leer `/home/dbbackup/incoming` (usa `sudo` o ajusta permisos) y la clave **privada** `age`, que debes traer tú.
* Si falta algún binlog en la secuencia, avisa y repite solo hasta antes del hueco (reproducir saltándose uno dejaría datos incoherentes).
* Cuando el primario se recupere, haz un dump de la BD promovida antes de volver.
* Recuerda actualizar `DATABASE_USER/PASS/NAME` de la app a los `MYSQL_*` del `db/.env` del secundario.

## Pruebas

```bash
python -m pytest tests/backup -q          # unitarios, sin Docker ni BD (~1 s)
bash tests/backup/e2e/run_e2e.sh          # integración completa con MariaDB, rsync/SSH y age en Docker (~5 min)
```

`run_e2e.sh` monta una réplica del proyecto en un directorio temporal y ejecuta los `.sh` reales: dump, binlogs, envío al
"secundario" (sshd con `rrsync -wo`), secundario caído y reintento, retención, `restore.sh` (inspect, simulacro, `--apply`,
fuente `archive`), cuenta restringida y `promote-secondary.sh`. Ejecútalo antes de fusionar cambios en `dbbackup/`, `scripts/` o el compose.

## Variables (`docker/.env`, ver `docker/.env.backup.example`)

| Variable | Defecto | Descripción |
|---|---|---|
| `BACKUP_DB_NAME`, `BACKUP_DB_USER`, `BACKUP_DB_PASSWORD` | — / `backup` / — | Usuario de solo lectura (no root) |
| `BACKUP_DUMP_HOUR`, `BACKUP_DUMP_MINUTE` | 4, 0 | Hora del dump diario. Si el contenedor estaba apagado a esa hora, lo hace al arrancar |
| `BACKUP_BINLOG_SHIP_HOURS` | 6 | Cada cuánto se archivan y envían los binlogs cerrados |
| `BACKUP_LOCAL_KEEP_DUMPS` | 2 | Dumps locales que se conservan (los no entregados no se borran, máx. 7) |
| `BACKUP_LOCAL_BINLOG_DAYS` | 7 | Días de binlogs archivados en el primario (si ya se enviaron) |
| `BACKUP_REMOTE_HOST/PORT/USER/PATH` | — / 22 / `dbbackup` / `/` | Secundario. Sin `HOST` solo hay copias locales |
| `BACKUP_AGE_RECIPIENT` | — | Clave **pública** `age1...` con la que se cifra lo que sale del primario |
| `BACKUP_KUMA_PUSH_URL` | — | Monitor Push de Uptime Kuma |
| `RESTORE_DB_ROOT_PASSWORD` | `restore-scratch` | Contraseña de la BD temporal (no se publica ningún puerto) |

## Decisiones y por qué

* **Binlog en vez de incrementales de `mariabackup`**: da precisión de segundos y no necesita acceso físico al datadir.
* **Dump local sin cifrar, dump enviado cifrado**: el local vive junto a los datos reales (mismo nivel de exposición) y permite restaurar sin
  claves a mano; lo que sale del servidor (a una máquina con otros servicios) va cifrado con una clave que solo tú tienes.
* **Un solo contenedor** con un bucle: tras descartar el streaming continuo de binlogs no hay nada que justifique dos servicios.
* **Usuario `backup` ≠ root** y el contenedor no ve el `.env` de la app ni `private/`.
* **El estado se persiste** (`/backups/state/state.json`): un reinicio no repite el dump ni pierde qué está pendiente de enviar.
* **`--source archive` y envío "solo cerrados"**: el binlog activo se sigue escribiendo; solo se copia cuando se cierra
  (`FLUSH BINARY LOGS` cada 6 h y tras el dump).
* **Clave SSH copiada a un fichero 0600 antes de cada envío**: OpenSSH rechaza claves cuyo dueño no es el usuario que ejecuta `ssh`
  (la clave montada pertenece a `ubuntu`, uid 1000, y el contenedor corre como root).
