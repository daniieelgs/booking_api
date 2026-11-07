#!/usr/bin/env bash
# EMERGENCY: bring up a MariaDB on the SECONDARY server from the latest backup received from the primary.
# Use it when the primary cannot be restored quickly and the secondary must take 100% of the load.
#
#   ./scripts/promote-secondary.sh --age-key /path/to/age-private-key.txt [options]
#
# What it does (it never modifies the primary, the secondary's existing containers, or its .env):
#   1. picks the newest COMPLETE dump (data + meta) in the incoming directory and the contiguous binlogs after it;
#   2. starts a new container "booking-db-promoted" (mariadb:10.5.19, own volume, network alias database-promoted);
#   3. decrypts with your private key and streams dump + binlogs straight into it (no plaintext on disk);
#   4. prints the row counts and the exact steps to point the secondary's app at the new database.
#
# Data loss: whatever happened after the last archived binlog (up to ~BINLOG_SHIP_HOURS, 6h by default)
# plus anything in a binlog that never arrived. The script tells you what the plan covers before it starts.
#
# Options:
#   --age-key FILE      REQUIRED. The age PRIVATE key (kept offline; never stored on the servers).
#   --backups-dir DIR   where the primary delivers files        (default /home/dbbackup/incoming)
#   --env-file FILE     DB env file with MYSQL_ROOT_PASSWORD, MYSQL_DATABASE, MYSQL_USER, MYSQL_PASSWORD (default db/.env)
#   --network NAME      docker network of the secondary's app stack (default docker_default)
#   --name NAME         container name                           (default booking-db-promoted)
#   --plan-only         only show what would be restored and exit (safe, changes nothing)
#   --yes               do not ask for confirmation
set -euo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"
# Absolute path usable by docker -v (native C:/... form under Git Bash on Windows; plain pwd on Linux).
hostpath() { (cd "$1" && { pwd -W 2>/dev/null || pwd; }); }

AGE_KEY=""; BACKUPS_DIR="/home/dbbackup/incoming"; ENV_FILE="db/.env"; NETWORK="docker_default"
NAME="booking-db-promoted"; PLAN_ONLY=0; YES=0

usage() { sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }
while [ $# -gt 0 ]; do
  case "$1" in
    --age-key)     AGE_KEY="${2:-}"; shift 2 ;;
    --backups-dir) BACKUPS_DIR="${2:-}"; shift 2 ;;
    --env-file)    ENV_FILE="${2:-}"; shift 2 ;;
    --network)     NETWORK="${2:-}"; shift 2 ;;
    --name)        NAME="${2:-}"; shift 2 ;;
    --plan-only)   PLAN_ONLY=1; shift ;;
    --yes)         YES=1; shift ;;
    -h|--help)     usage 0 ;;
    *) echo "Unknown option: $1" >&2; usage 2 ;;
  esac
done

[[ "$NAME" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]] || { echo "ERROR: invalid --name" >&2; exit 2; }
[[ "$NETWORK" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]] || { echo "ERROR: invalid --network" >&2; exit 2; }
[ -d "$BACKUPS_DIR" ] || { echo "ERROR: backups dir $BACKUPS_DIR does not exist or is not readable" >&2; exit 1; }
if [ "$PLAN_ONLY" != 1 ]; then
  [ -n "$AGE_KEY" ] || { echo "ERROR: --age-key is required" >&2; usage 2; }
  [ -f "$AGE_KEY" ] || { echo "ERROR: age key file $AGE_KEY not found" >&2; exit 1; }
  [ -f "$ENV_FILE" ] || { echo "ERROR: $ENV_FILE not found" >&2; exit 1; }
  AGE_KEY="$(hostpath "$(dirname "$AGE_KEY")")/$(basename "$AGE_KEY")"
fi
BACKUPS_DIR="$(hostpath "$BACKUPS_DIR")"

# Tools image: age + mariadb client + python (the dbbackup code is mounted read-only from this checkout).
if ! docker image inspect booking-backup >/dev/null 2>&1; then
  echo "Building the booking-backup image (needed for age and the restore plan)..."
  docker build -t booking-backup - < docker/Dockerfile.backup
fi
tools() { docker run --rm -i "$@"; }

echo "Reading the backup directory $BACKUPS_DIR ..."
PLAN_OUT="$(tools -v "$BACKUPS_DIR":/in:ro -v "$(hostpath "$REPO_ROOT")/dbbackup":/opt/dbbackup:ro booking-backup \
              python3 -m dbbackup.promote_plan --dir /in)" || { echo "ERROR: no usable backup found" >&2; exit 1; }
eval "$PLAN_OUT"

echo
echo "=== Restore plan ==="
echo "  Base dump:    $PLAN_DUMP  (taken $PLAN_CREATED)"
echo "  Binlogs:      ${#PLAN_BINLOGS[@]} file(s) to roll forward from $PLAN_BINLOG_FILE position $PLAN_BINLOG_POS"
if [ "${#PLAN_BINLOGS[@]}" -gt 0 ]; then
  echo "  Last binlog:  ${PLAN_BINLOGS[${#PLAN_BINLOGS[@]}-1]}"
fi
if [ "${#PLAN_GAPS[@]}" -gt 0 ]; then
  echo "  WARNING: missing binlog(s): ${PLAN_GAPS[*]}"
  echo "           Replay stops before the first gap; later changes cannot be recovered."
fi
echo "  Data newer than the last archived binlog will be LOST."
echo

[ "$PLAN_ONLY" = 1 ] && exit 0

if docker container inspect "$NAME" >/dev/null 2>&1; then
  echo "ERROR: container $NAME already exists. Remove it first (and its volume ${NAME}-data) if you really want to redo the promotion." >&2
  exit 1
fi
docker network inspect "$NETWORK" >/dev/null 2>&1 || { echo "ERROR: docker network $NETWORK not found (use --network)" >&2; exit 1; }

if [ "$YES" != 1 ]; then
  read -r -p "Start $NAME and restore this backup into it? [y/N] " answer
  [[ "$answer" =~ ^[yY]$ ]] || { echo "Aborted."; exit 1; }
fi

# Decrypt + decompress to stdout. Plaintext only ever travels through pipes, never touches the disk.
decrypt_stream() {
  tools -e F="$1" -v "$AGE_KEY":/key:ro -v "$BACKUPS_DIR":/in:ro booking-backup \
        sh -c 'age -d -i /key "/in/$F" | gunzip'
}

SQL_NOBINLOG='SET SESSION sql_log_bin=0'

echo "Starting $NAME ..."
docker run -d --name "$NAME" --restart unless-stopped \
  --network "$NETWORK" --network-alias database-promoted \
  --env-file "$ENV_FILE" -e TZ=Europe/Madrid \
  -v "${NAME}-data":/var/lib/mysql \
  mariadb:10.5.19 \
  --log-bin=mysql-bin --binlog-format=ROW --binlog-row-image=FULL --server-id=2 --expire-logs-days=7 --sync-binlog=1 \
  >/dev/null

echo -n "Waiting for the database to accept connections"
ready=0
for _ in $(seq 1 90); do
  # Over TCP on purpose: during first start the entrypoint runs a temporary socket-only server for the
  # initialisation, which answers a socket ping before the real server (the one that stays) is up.
  if docker exec "$NAME" sh -c 'mysqladmin ping -h127.0.0.1 -P3306 --protocol=TCP -uroot -p"$MYSQL_ROOT_PASSWORD" --silent' >/dev/null 2>&1; then ready=1; break; fi
  echo -n "."; sleep 2
done
echo
[ "$ready" = 1 ] || { echo "ERROR: $NAME did not become ready. Check: docker logs $NAME" >&2; exit 1; }

echo "Loading the dump ($PLAN_DUMP) ..."
decrypt_stream "$PLAN_DUMP" | docker exec -i "$NAME" sh -c "exec mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" --init-command='$SQL_NOBINLOG'"

first=1
for f in "${PLAN_BINLOGS[@]}"; do
  echo "Replaying $f ..."
  start_opt=""
  [ "$first" = 1 ] && start_opt="--start-position=$PLAN_BINLOG_POS"
  decrypt_stream "$f" | docker exec -i "$NAME" sh -c \
    "mysqlbinlog $start_opt --database=\"\$MYSQL_DATABASE\" - | mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" --init-command='$SQL_NOBINLOG'"
  first=0
done

echo
echo "=== Verification ==="
docker exec "$NAME" sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" -t -e "SELECT COUNT(*) AS bookings, MAX(datetime_created) AS newest_booking FROM booking; SELECT COUNT(*) AS locals FROM local;"' \
  || echo "(could not run the verification query; check the data manually)"

cat <<EOF

=== Database restored in container "$NAME" ===
It is reachable on network "$NETWORK" as host "database-promoted", port 3306.
The application database user is the MYSQL_USER/MYSQL_PASSWORD from $ENV_FILE.

To make the secondary serve everything (do it deliberately, this script did not change anything else):
  1. In the secondary's .env set:   DATABASE_HOST=database-promoted   DATABASE_PORT=3306
     (DATABASE_USER / DATABASE_PASS / DATABASE_NAME must match MYSQL_USER / MYSQL_PASSWORD / MYSQL_DATABASE of $ENV_FILE)
  2. Restart the app containers:     docker restart docker-web-1 docker-worker-1 docker-beat-1
  3. Check:                          curl -s http://localhost:5001/health
  4. Point traffic (DNS / front proxy) to the secondary if it is not already receiving it.
When the primary is healthy again, take a fresh dump from the promoted database before switching back.
EOF
