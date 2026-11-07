#!/usr/bin/env bash
# Creates (or updates the password of) the least-privilege MariaDB user used by the backup service.
#
# Run once on the primary, from anywhere:   ./scripts/create-backup-db-user.sh
# Safe to re-run: it is idempotent and also rotates the password to the current BACKUP_DB_PASSWORD.
#
# The password travels through stdin only (never in a command line or in `ps`).
# The root password is read inside the database container from its own environment.
set -euo pipefail

cd "$(dirname "$0")/.."

ENV_FILE="${COMPOSE_ENV_FILE:-./docker/.env}"
COMPOSE_FILE_PATH="${COMPOSE_FILE_PATH:-./docker/docker-compose.prod.yml}"
HOST_PATTERN="${BACKUP_DB_HOST_PATTERN:-}"   # empty = detect the compose network's subnet; never '%' (port 3307 is published)

[ -f "$ENV_FILE" ] || { echo "ERROR: $ENV_FILE not found" >&2; exit 1; }

# Read only the variables we need, without sourcing the whole file.
get_var() { grep -E "^$1=" "$ENV_FILE" | tail -n1 | cut -d= -f2- | sed -E 's/[[:space:]]+#.*$//; s/^"(.*)"$/\1/'; }
BACKUP_DB_USER="$(get_var BACKUP_DB_USER)"; BACKUP_DB_USER="${BACKUP_DB_USER:-backup}"
BACKUP_DB_PASSWORD="$(get_var BACKUP_DB_PASSWORD)"

[ -n "$BACKUP_DB_PASSWORD" ] || { echo "ERROR: BACKUP_DB_PASSWORD is not set in $ENV_FILE" >&2; exit 1; }
[[ "$BACKUP_DB_USER" =~ ^[A-Za-z0-9_]+$ ]] || { echo "ERROR: BACKUP_DB_USER must be [A-Za-z0-9_]" >&2; exit 1; }
[[ "$BACKUP_DB_PASSWORD" =~ ^[A-Za-z0-9_.@%+=-]+$ ]] || { echo "ERROR: BACKUP_DB_PASSWORD may only contain A-Za-z0-9_.@%+=-" >&2; exit 1; }

COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE_PATH")

# a.b.c.d/24 prefix -> 255.255.255.0 (MariaDB accepts "network/netmask" as the host part of an account)
cidr_to_mask() {
  local p="$1" mask="" i octet
  for i in 1 2 3 4; do
    if [ "$p" -ge 8 ]; then octet=255; p=$((p - 8))
    elif [ "$p" -gt 0 ]; then octet=$((256 - (1 << (8 - p)))); p=0
    else octet=0; fi
    mask+="${mask:+.}$octet"
  done
  echo "$mask"
}

# The backup container connects from the compose network, whose subnet is NOT always 172.x (it depends on
# the machine's Docker address pools), so the account is restricted to the actual subnet instead of guessing.
detect_host_pattern() {
  local cid net cidr
  cid="$("${COMPOSE[@]}" ps -q database 2>/dev/null | head -n1)"
  [ -n "$cid" ] || return 1
  net="$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$cid" | awk '{print $1}')"
  [ -n "$net" ] || return 1
  cidr="$(docker network inspect -f '{{range .IPAM.Config}}{{.Subnet}} {{end}}' "$net" | tr ' ' '\n' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+/[0-9]+$' | head -n1)"
  [ -n "$cidr" ] || return 1
  echo "${cidr%/*}/$(cidr_to_mask "${cidr#*/}")"
}

if [ -z "$HOST_PATTERN" ]; then
  if HOST_PATTERN="$(detect_host_pattern)"; then
    echo "Detected the compose network subnet: $HOST_PATTERN"
  else
    HOST_PATTERN="172.%"
    echo "WARNING: could not detect the compose network subnet, falling back to $HOST_PATTERN" >&2
  fi
fi
[[ "$HOST_PATTERN" =~ ^[A-Za-z0-9_.%/]+$ ]] || { echo "ERROR: invalid BACKUP_DB_HOST_PATTERN: $HOST_PATTERN" >&2; exit 1; }

# Privileges, and why each one is needed:
#   SELECT, SHOW VIEW, TRIGGER, EVENT, LOCK TABLES  -> mysqldump of the data, routines, triggers and events
#   RELOAD                                           -> FLUSH BINARY LOGS / mysqldump --flush-logs --master-data
#   REPLICATION CLIENT                               -> SHOW BINARY LOGS / SHOW MASTER STATUS
#   REPLICATION SLAVE                                -> mysqlbinlog --read-from-remote-server (fetch binlogs)
# No INSERT/UPDATE/DELETE/DROP/ALTER: the backup user can read everything and change nothing.
"${COMPOSE[@]}" exec -T database sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD"' <<SQL
CREATE USER IF NOT EXISTS '${BACKUP_DB_USER}'@'${HOST_PATTERN}' IDENTIFIED BY '${BACKUP_DB_PASSWORD}';
ALTER USER '${BACKUP_DB_USER}'@'${HOST_PATTERN}' IDENTIFIED BY '${BACKUP_DB_PASSWORD}';
GRANT SELECT, SHOW VIEW, TRIGGER, EVENT, LOCK TABLES, RELOAD, REPLICATION CLIENT, REPLICATION SLAVE
  ON *.* TO '${BACKUP_DB_USER}'@'${HOST_PATTERN}';
FLUSH PRIVILEGES;
SQL

echo "User '${BACKUP_DB_USER}'@'${HOST_PATTERN}' is ready (read-only + replication privileges)."
echo "Next: restart the database once to enable the binary log (see docs/db-backups.md), then start the 'backup' service."
