#!/usr/bin/env bash
# Recover rows that were deleted by mistake, WITHOUT touching or stopping the live database.
#
#   1. Find the moment of the mistake:
#        ./scripts/restore.sh --inspect [--since "2026-11-07 09:00:00"]
#      (lists DELETE/UPDATE row events with their timestamps)
#
#   2. Reconstruct the database as it was just before it and generate the SQL for the lost rows (dry run):
#        ./scripts/restore.sh --until "2026-11-07 10:31:50" [--tables booking,service_booking]
#
#   3. Review the printed summary / SQL file, then insert the rows into the live database:
#        ./scripts/restore.sh --until "2026-11-07 10:31:50" --apply
#
# How it works: the newest local dump taken before --until is loaded into a throw-away MariaDB
# (compose profile "restore"), the binary logs are replayed on top of it up to --until, and every row
# that exists there but is missing from the live database is turned into INSERT IGNORE statements.
# Rows that still exist are never modified (INSERT IGNORE), and the throw-away database is always destroyed.
#
# Options:
#   --source live|archive   where binlogs come from (default live = the running server; use archive when
#                           the server no longer has them, e.g. they were purged after 7 days)
#   --yes                   do not ask for confirmation with --apply
#
# Environment overrides: COMPOSE_ENV_FILE (default ./docker/.env), COMPOSE_FILE_PATH (default ./docker/docker-compose.prod.yml)
set -euo pipefail

cd "$(dirname "$0")/.."

ENV_FILE="${COMPOSE_ENV_FILE:-./docker/.env}"
COMPOSE_FILE_PATH="${COMPOSE_FILE_PATH:-./docker/docker-compose.prod.yml}"
COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE_PATH")

usage() { sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

MODE=""; UNTIL=""; SINCE=""; TABLES=""; SOURCE="live"; APPLY=0; YES=0
while [ $# -gt 0 ]; do
  case "$1" in
    --inspect) MODE="inspect"; shift ;;
    --until)   UNTIL="${2:-}"; MODE="${MODE:-restore}"; shift 2 ;;
    --since)   SINCE="${2:-}"; shift 2 ;;
    --tables)  TABLES="${2:-}"; shift 2 ;;
    --source)  SOURCE="${2:-}"; shift 2 ;;
    --apply)   APPLY=1; shift ;;
    --yes)     YES=1; shift ;;
    -h|--help) usage 0 ;;
    *) echo "Unknown option: $1" >&2; usage 2 ;;
  esac
done

[ -f "$ENV_FILE" ] || { echo "ERROR: $ENV_FILE not found" >&2; exit 1; }
[ -n "$MODE" ] || usage 2
[[ "$SOURCE" =~ ^(live|archive)$ ]] || { echo "ERROR: --source must be live or archive" >&2; exit 2; }
if [ "$MODE" = "restore" ]; then
  [[ "$UNTIL" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}\ [0-9]{2}:[0-9]{2}:[0-9]{2}$ ]] || { echo 'ERROR: --until must look like "2026-11-07 10:31:50"' >&2; exit 2; }
fi
if [ -n "$SINCE" ]; then
  [[ "$SINCE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}\ [0-9]{2}:[0-9]{2}:[0-9]{2}$ ]] || { echo 'ERROR: --since must look like "2026-11-07 09:00:00"' >&2; exit 2; }
fi
if [ -n "$TABLES" ]; then
  [[ "$TABLES" =~ ^[A-Za-z0-9_,]+$ ]] || { echo "ERROR: --tables must be a comma separated list of table names" >&2; exit 2; }
fi
if [ "$APPLY" = 1 ] && [ "$MODE" != "restore" ]; then
  echo "ERROR: --apply only makes sense together with --until" >&2; exit 2
fi

# The backup container must be reachable: `run` starts a one-off container on the compose network.
run_backup() { "${COMPOSE[@]}" run --rm --no-deps -T backup "$@"; }

if [ "$MODE" = "inspect" ]; then
  args=(python3 -m dbbackup.restore inspect)
  [ -n "$SINCE" ] && args+=(--since "$SINCE")
  run_backup "${args[@]}"
  exit 0
fi

OUT_NAME="recovered-$(date +%Y%m%dT%H%M%S).sql"
OUT_PATH="/backups/restore/$OUT_NAME"

cleanup() {
  echo "Destroying the throw-away database..."
  "${COMPOSE[@]}" --profile restore rm -sfv restore-db >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Starting the throw-away database (restore-db)..."
"${COMPOSE[@]}" --profile restore up -d restore-db

args=(python3 -m dbbackup.restore run --until "$UNTIL" --source "$SOURCE" --out "$OUT_PATH")
[ -n "$TABLES" ] && args+=(--tables "$TABLES")
run_backup "${args[@]}"

if [ "$APPLY" != 1 ]; then
  echo
  echo "DRY RUN: nothing was changed in the live database."
  echo "Review the SQL:  docker compose --env-file $ENV_FILE -f $COMPOSE_FILE_PATH run --rm --no-deps -T backup cat $OUT_PATH"
  echo "Apply it with:   $0 --until \"$UNTIL\"${TABLES:+ --tables $TABLES} --source $SOURCE --apply"
  exit 0
fi

if [ "$YES" != 1 ]; then
  read -r -p "Insert the rows listed above into the LIVE database? [y/N] " answer
  [[ "$answer" =~ ^[yY]$ ]] || { echo "Aborted. Nothing was changed."; exit 1; }
fi

echo "Applying $OUT_NAME to the live database..."
# The root password is read inside the database container from its own environment: it never touches this host.
run_backup cat "$OUT_PATH" | "${COMPOSE[@]}" exec -T database sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"'
echo "Done. The SQL file is kept in the backup volume at $OUT_PATH"
