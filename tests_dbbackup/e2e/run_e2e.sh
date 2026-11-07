#!/usr/bin/env bash
# End-to-end test of the whole backup system with REAL components in Docker:
# MariaDB 10.5.19 (binlog on), the backup service, rsync/rrsync over SSH to a "secondary", age encryption,
# restore.sh (inspect / dry-run / apply / archive source) and promote-secondary.sh.
#
# Needs Docker + Docker Compose v2 + ssh-keygen. Takes a few minutes. Touches nothing outside Docker objects
# named e2e* / project "e2ebk" and a temp directory. Run it from anywhere:
#
#     bash tests_dbbackup/e2e/run_e2e.sh
#
# The unit tests (python -m pytest tests_dbbackup) need no Docker; this one is the integration check you
# run before merging changes to the backup system.
set -euo pipefail
export MSYS_NO_PATHCONV=1        # Git Bash on Windows must not rewrite /paths passed to docker
export COMPOSE_PROJECT_NAME=e2ebk
export MSYS2_ARG_CONV_EXCL='*'

SRC="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="${E2E_WORK:-$(mktemp -d)}"
mkdir -p "$WORK"
PROJ="$WORK/proj"
# Paths handed to docker.exe (build contexts, -v mounts) must be native on Windows (C:/...); on Linux pwd -W does not exist.
W() { (cd "$1" 2>/dev/null && { pwd -W 2>/dev/null || pwd; }); }
KEEP="${E2E_KEEP:-0}"
FAILS=0
STEP=0

c_ok=$'\033[32m'; c_bad=$'\033[31m'; c_off=$'\033[0m'
step()  { STEP=$((STEP+1)); echo; echo "=== [$STEP] $*"; }
pass()  { echo "  ${c_ok}PASS${c_off} $*"; }
fail()  { echo "  ${c_bad}FAIL${c_off} $*"; FAILS=$((FAILS+1)); }
check() { # check "description" expected actual
  if [ "$2" = "$3" ]; then pass "$1 ($3)"; else fail "$1: expected [$2] got [$3]"; fi
}
contains() { # contains "description" needle haystack
  if grep -qF -- "$2" <<<"$3"; then pass "$1"; else fail "$1: [$2] not found in: $(head -c 600 <<<"$3")"; fi
}
absent() {
  if grep -qF -- "$2" <<<"$3"; then fail "$1: [$2] unexpectedly present"; else pass "$1"; fi
}

DC() { (cd "$PROJ" && docker compose --env-file ./docker/.env -f ./docker/docker-compose.prod.yml "$@"); }
sql() { DC exec -T database sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" bbdd -N -B -e "$1"' sh "$1" 2>/dev/null; }
in_backup() { DC exec -T backup "$@"; }

cleanup() {
  local rc=$?
  echo; echo "=== cleanup"
  docker rm -f e2e-promoted e2e-secondary >/dev/null 2>&1 || true
  docker volume rm -f e2e-promoted-data >/dev/null 2>&1 || true
  [ -d "$PROJ" ] && DC --profile restore down -v --remove-orphans >/dev/null 2>&1 || true
  docker network rm e2ebk_default >/dev/null 2>&1 || true
  if [ "$KEEP" != 1 ]; then rm -rf "$WORK" 2>/dev/null || true; else echo "work dir kept: $WORK"; fi
  if [ $rc -ne 0 ] && [ "$FAILS" -eq 0 ]; then echo "${c_bad}aborted (rc=$rc) before finishing${c_off}"; fi
}
trap cleanup EXIT

# ------------------------------------------------------------------------------------------------
step "Mirror the project layout in $WORK (so the real scripts and compose file run unchanged)"
rm -rf "$PROJ"; mkdir -p "$PROJ/docker/secrets" "$PROJ/db" "$PROJ/scripts" "$WORK/secondary"
cp -r "$SRC/dbbackup" "$PROJ/dbbackup"
find "$PROJ/dbbackup" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
cp "$SRC/docker/docker-compose.prod.yml" "$SRC/docker/Dockerfile.backup" "$PROJ/docker/"
for f in "$SRC"/scripts/*.sh; do sed 's/\r$//' "$f" > "$PROJ/scripts/$(basename "$f")"; chmod +x "$PROJ/scripts/$(basename "$f")"; done
touch "$PROJ/docker/secrets/.gitkeep"

cat > "$PROJ/db/.env" <<'EOF'
MYSQL_ROOT_PASSWORD=rootpw_e2e
MYSQL_DATABASE=bbdd
MYSQL_USER=app
MYSQL_PASSWORD=apppw_e2e
EOF

# A schema shaped like the real one: FK with ON DELETE CASCADE and BEFORE INSERT triggers.
cat > "$PROJ/db/init.sql" <<'EOF'
CREATE TABLE status (id INT PRIMARY KEY, status CHAR(1) NOT NULL UNIQUE);
INSERT INTO status VALUES (1,'P'),(2,'C'),(3,'D'),(4,'X');
CREATE TABLE booking (
  id INT PRIMARY KEY AUTO_INCREMENT, client_name VARCHAR(45), status_id INT NOT NULL,
  datetime_created DATETIME NOT NULL, datetime_updated DATETIME NOT NULL,
  FOREIGN KEY (status_id) REFERENCES status(id));
CREATE TABLE service_booking (
  id INT PRIMARY KEY AUTO_INCREMENT, booking_id INT NOT NULL, service VARCHAR(45),
  FOREIGN KEY (booking_id) REFERENCES booking(id) ON DELETE CASCADE);
CREATE TABLE local (id CHAR(32) PRIMARY KEY, name VARCHAR(45));
DELIMITER $$
CREATE TRIGGER before_insert_booking BEFORE INSERT ON booking FOR EACH ROW
BEGIN SET NEW.datetime_created = NOW(); SET NEW.datetime_updated = NOW(); END $$
DELIMITER ;
INSERT INTO local VALUES ('151b1bf60f3e4026814183ffe9c75148','SUBLIME');
INSERT INTO booking (id, client_name, status_id) VALUES (1,'ana',2),(2,'beto',2),(3,'carla',1),(4,'dani',2),(5,'eva',4);
INSERT INTO service_booking (booking_id, service) VALUES (1,'corte'),(2,'corte'),(2,'barba'),(3,'tinte'),(4,'corte'),(5,'corte');
EOF

# ------------------------------------------------------------------------------------------------
step "Build the backup image and create the keys (age for encryption, ssh for delivery)"
docker build -q -t booking-backup - < "$PROJ/docker/Dockerfile.backup" >/dev/null
for tool in mariadb-dump mariadb mariadb-binlog age age-keygen rsync ssh ssh-keyscan; do
  if docker run --rm booking-backup sh -c "command -v $tool" >/dev/null 2>&1; then pass "image provides $tool"; else fail "image is missing $tool"; fi
done

docker run --rm booking-backup age-keygen > "$WORK/age_key.txt" 2>/dev/null
AGE_RECIPIENT="$(docker run --rm -i booking-backup age-keygen -y < "$WORK/age_key.txt")"
case "$AGE_RECIPIENT" in age1*) pass "age key pair generated";; *) fail "age keygen failed: $AGE_RECIPIENT";; esac

rm -f "$PROJ/docker/secrets/backup_ssh_key" "$PROJ/docker/secrets/backup_ssh_key.pub"
ssh-keygen -q -t ed25519 -N '' -C e2e -f "$PROJ/docker/secrets/backup_ssh_key"
# docker/secrets must not be needed after the key is in the image build context for the secondary
cp "$PROJ/docker/secrets/backup_ssh_key.pub" "$WORK/secondary/backup_ssh_key.pub"

cat > "$PROJ/docker/.env" <<EOF
# compose validates every service of the file even when only some are started: the web service needs these to parse
SSL_CERT_FILE=/dev/null
SSL_KEY_FILE=/dev/null
SERVER_NAME=e2e
REDIS_PASSWORD=e2e
DB_PORT=33307
BACKUP_DB_NAME=bbdd
BACKUP_DB_USER=backup
BACKUP_DB_PASSWORD=backuppw_e2e
BACKUP_AGE_RECIPIENT=$AGE_RECIPIENT
BACKUP_REMOTE_HOST=secondary
BACKUP_REMOTE_USER=dbbackup
BACKUP_REMOTE_PATH=/
BACKUP_BINLOG_SHIP_HOURS=6
EOF

# ------------------------------------------------------------------------------------------------
step "Start MariaDB with the compose file's real binlog flags"
DC up -d database >/dev/null 2>&1
for i in $(seq 1 90); do
  if DC exec -T database sh -c 'mysqladmin ping -uroot -p"$MYSQL_ROOT_PASSWORD" --silent' >/dev/null 2>&1 \
     && [ "$(sql 'SELECT COUNT(*) FROM booking' || true)" = "5" ]; then break; fi
  sleep 2
done
check "seed data loaded by init.sql" "5" "$(sql 'SELECT COUNT(*) FROM booking')"
check "binary log is enabled" "ON" "$(sql "SELECT @@log_bin" | sed 's/^1$/ON/')"
check "binlog format is ROW" "ROW" "$(sql 'SELECT @@binlog_format')"
check "binlog basename is fixed (not the hostname)" "mysql-bin" "$(sql 'SELECT @@log_bin_basename' | sed 's#.*/##')"

# ------------------------------------------------------------------------------------------------
step "create-backup-db-user.sh creates a read-only user"
(cd "$PROJ" && ./scripts/create-backup-db-user.sh) | tail -2
BACKUP_HOST="$(sql "SELECT host FROM mysql.user WHERE user='backup'")"
echo "    backup user is restricted to host: $BACKUP_HOST"
case "$BACKUP_HOST" in "%"|"") fail "backup user must not be reachable from any host";; *) pass "backup user limited to the compose subnet";; esac
GRANTS="$(sql "SHOW GRANTS FOR 'backup'@'$BACKUP_HOST'")"
contains "has REPLICATION SLAVE" "REPLICATION SLAVE" "$GRANTS"
contains "has SELECT" "SELECT" "$GRANTS"
absent  "cannot write (no INSERT)" "INSERT" "$GRANTS"
absent  "cannot drop/alter" "ALL PRIVILEGES" "$GRANTS"
(cd "$PROJ" && ./scripts/create-backup-db-user.sh >/dev/null) && pass "re-running the script is idempotent"

# ------------------------------------------------------------------------------------------------
step "Start the 'secondary': sshd with a restricted account (forced rrsync, write-only)"
cat > "$WORK/secondary/Dockerfile" <<'EOF'
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y --no-install-recommends openssh-server rsync python3 && rm -rf /var/lib/apt/lists/* && mkdir -p /run/sshd
RUN useradd -m -s /bin/sh dbbackup && passwd -l dbbackup >/dev/null && mkdir -p /home/dbbackup/incoming /home/dbbackup/.ssh \
 && chown -R dbbackup:dbbackup /home/dbbackup && chmod 700 /home/dbbackup/.ssh
COPY backup_ssh_key.pub /tmp/pub
RUN RRSYNC="$(command -v rrsync || ls /usr/share/doc/rsync/scripts/rrsync 2>/dev/null | head -1)" \
 && printf 'restrict,command="%s -wo /home/dbbackup/incoming" %s\n' "$RRSYNC" "$(cat /tmp/pub)" > /home/dbbackup/.ssh/authorized_keys \
 && chown dbbackup:dbbackup /home/dbbackup/.ssh/authorized_keys && chmod 600 /home/dbbackup/.ssh/authorized_keys \
 && printf 'PasswordAuthentication no\nPermitRootLogin no\n' > /etc/ssh/sshd_config.d/hardening.conf
CMD ["/usr/sbin/sshd","-D","-e"]
EOF
docker build -q -t e2e-secondary "$(W "$WORK/secondary")" >/dev/null
docker network inspect e2ebk_default >/dev/null 2>&1 || docker network create e2ebk_default >/dev/null
docker run -d --name e2e-secondary --network e2ebk_default --network-alias secondary e2e-secondary >/dev/null
sleep 3
docker run --rm --network e2ebk_default booking-backup ssh-keyscan -t ed25519 secondary 2>/dev/null > "$PROJ/docker/secrets/backup_known_hosts"
contains "host key pinned" "ssh-ed25519" "$(cat "$PROJ/docker/secrets/backup_known_hosts")"

# ------------------------------------------------------------------------------------------------
step "Start the backup service: first run must dump, archive binlogs and deliver (no 04:00 wait)"
DC up -d backup >/dev/null 2>&1
INCOMING=""
for i in $(seq 1 60); do
  INCOMING="$(docker exec e2e-secondary ls /home/dbbackup/incoming 2>/dev/null || true)"
  if grep -q 'meta.json' <<<"$INCOMING"; then break; fi
  sleep 3
done
echo "$INCOMING" | sed 's/^/    secondary: /'
contains "encrypted dump arrived" ".sql.gz.age" "$INCOMING"
contains "dump meta arrived"      ".meta.json" "$INCOMING"
if grep -qE '\.sql\.gz$' <<<"$INCOMING"; then fail "plaintext dump leaked to the secondary"; else pass "no plaintext dump leaked to the secondary"; fi
STATUS="$(in_backup cat /backups/state/status.json)"
contains "service reports state" '"healthy"' "$STATUS"
check "container healthcheck passes" "0" "$(in_backup python3 -m dbbackup.healthcheck >/dev/null 2>&1; echo $?)"
LOCAL="$(in_backup ls /backups/dumps)"
contains "local dump kept on the primary" ".sql.gz" "$LOCAL"

DUMP1="$(in_backup sh -c 'ls /backups/dumps/*.sql.gz | head -1')"
check "local dump is a complete gzip mysqldump" "1" "$(in_backup sh -c "gunzip -c $DUMP1 | grep -c 'Dump completed'")"
contains "dump records the binlog position" "MASTER_LOG_FILE" "$(in_backup sh -c "gunzip -c $DUMP1 | head -40")"

# ------------------------------------------------------------------------------------------------
step "Simulate the incident: changes after the dump, then an accidental DELETE, then legit new data"
sql "INSERT INTO booking (id, client_name, status_id) VALUES (6,'fran',2),(7,'gema',2); INSERT INTO service_booking (booking_id, service) VALUES (6,'corte'),(7,'tinte');" >/dev/null
sleep 3
T_BEFORE="$(sql 'SELECT NOW()')"
sleep 3
sql "DELETE FROM booking WHERE id IN (2,3);" >/dev/null     # cascades to service_booking
T_DEL="$(sql 'SELECT NOW()')"
sleep 3
sql "INSERT INTO booking (id, client_name, status_id) VALUES (8,'hugo',2); INSERT INTO service_booking (booking_id, service) VALUES (8,'corte');" >/dev/null
echo "    before=$T_BEFORE  delete=$T_DEL"
check "live has lost the rows" "1,4,5,6,7,8" "$(sql 'SELECT GROUP_CONCAT(id ORDER BY id) FROM booking')"
check "cascade removed their services" "0" "$(sql 'SELECT COUNT(*) FROM service_booking WHERE booking_id IN (2,3)')"

# ------------------------------------------------------------------------------------------------
step "restore.sh --inspect finds the DELETE and its timestamp"
INSPECT="$(cd "$PROJ" && ./scripts/restore.sh --inspect 2>&1)"
echo "$INSPECT" | sed 's/^/    /'
contains "reports the deletion on booking" "DELETE  bbdd.booking  x2" "$INSPECT"
# FK cascades are applied by InnoDB itself and are NOT written to the binlog in ROW format, so only the booking DELETE is listed.
absent   "cascade deletes are not listed as separate events" "bbdd.service_booking" "$INSPECT"
contains "uses the delete's wall-clock second" "${T_DEL%:*}" "$INSPECT"

# ------------------------------------------------------------------------------------------------
step "restore.sh DRY RUN (live binlogs): reconstruct the past, change nothing"
OUT="$(cd "$PROJ" && ./scripts/restore.sh --until "$T_BEFORE" 2>&1)"
echo "$OUT" | tail -12 | sed 's/^/    /'
contains "2 bookings recovered" "booking: 2" "$OUT"
contains "their service rows recovered" "service_booking: 3" "$OUT"
contains "says it was a dry run" "DRY RUN" "$OUT"
check "live DB untouched by the dry run" "1,4,5,6,7,8" "$(sql 'SELECT GROUP_CONCAT(id ORDER BY id) FROM booking')"
SQLFILE="$(in_backup sh -c 'cat /backups/restore/recovered-*.sql | tail -n +1')"
contains "SQL uses INSERT IGNORE" "INSERT IGNORE INTO \`booking\`" "$SQLFILE"
contains "carla (id 3) is in the SQL" "carla" "$SQLFILE"
absent   "booking 8 (created after the delete) is NOT touched" "hugo" "$SQLFILE"
check "throw-away DB was destroyed" "" "$(docker ps -a --filter name=e2ebk-restore-db --format '{{.Names}}')"

# ------------------------------------------------------------------------------------------------
step "Same restore from the ARCHIVED binlogs (what you use when the server purged its own)"
in_backup python3 - <<'PY'
from dbbackup.config import Config
from dbbackup.state import State
from dbbackup import binlogs
cfg = Config.from_env(); st = State(cfg.state_dir / 'state.json')
binlogs.flush_binary_logs(cfg)
print('archived:', binlogs.archive_new_binlogs(cfg, st))
st.save()
PY
OUT2="$(cd "$PROJ" && ./scripts/restore.sh --until "$T_BEFORE" --source archive 2>&1)"
echo "$OUT2" | tail -6 | sed 's/^/    /'
contains "archive source: 2 bookings" "booking: 2" "$OUT2"
contains "archive source: service rows" "service_booking: 3" "$OUT2"

# ------------------------------------------------------------------------------------------------
step "restore.sh --apply inserts only what is missing"
APPLY_OUT="$(cd "$PROJ" && ./scripts/restore.sh --until "$T_BEFORE" --apply --yes 2>&1)" || { fail "restore.sh --apply failed"; echo "$APPLY_OUT" | tail -25 | sed 's/^/    | /'; }
check "deleted bookings are back, nothing else changed" "1,2,3,4,5,6,7,8" "$(sql 'SELECT GROUP_CONCAT(id ORDER BY id) FROM booking')"
check "their services are back" "3" "$(sql 'SELECT COUNT(*) FROM service_booking WHERE booking_id IN (2,3)')"
check "client data intact" "beto|carla" "$(sql "SELECT GROUP_CONCAT(client_name ORDER BY id SEPARATOR '|') FROM booking WHERE id IN (2,3)")"
check "booking created after the incident untouched" "hugo" "$(sql 'SELECT client_name FROM booking WHERE id=8')"
OUT3="$(cd "$PROJ" && ./scripts/restore.sh --until "$T_BEFORE" 2>&1)"
contains "idempotent: nothing left to recover" "TOTAL: 0" "$OUT3"
APPLY_OUT="$(cd "$PROJ" && ./scripts/restore.sh --until "$T_BEFORE" --apply --yes 2>&1)" || { fail "second --apply failed"; echo "$APPLY_OUT" | tail -15 | sed 's/^/    | /'; }
check "applying twice does not duplicate" "8" "$(sql 'SELECT COUNT(*) FROM booking')"

# ------------------------------------------------------------------------------------------------
step "Secondary DOWN: deliveries are retried later, nothing is lost"
docker stop e2e-secondary >/dev/null
in_backup python3 - <<'PY'
from datetime import datetime
from dbbackup.config import Config
from dbbackup.state import State
from dbbackup import dump, transfer
cfg = Config.from_env(); st = State(cfg.state_dir / 'state.json')
now = datetime.now()
dump.make_dump(cfg, now)
res = transfer.send_pending(cfg, st, now)
st.save()
print('failed =', res.failed)
print('pending =', len(transfer.pending(cfg, st)))
PY
PENDING_DOWN="$(in_backup python3 -c "
from dbbackup.config import Config; from dbbackup.state import State; from dbbackup import transfer
cfg=Config.from_env(); print(len(transfer.pending(cfg, State(cfg.state_dir/'state.json'))))")"
if [ "$PENDING_DOWN" -ge 2 ]; then pass "backups stay pending while the secondary is down ($PENDING_DOWN)"; else fail "expected pending items, got $PENDING_DOWN"; fi
docker start e2e-secondary >/dev/null; sleep 4
in_backup python3 - <<'PY'
from datetime import datetime
from dbbackup.config import Config
from dbbackup.state import State
from dbbackup import transfer
cfg = Config.from_env(); st = State(cfg.state_dir / 'state.json')
res = transfer.send_pending(cfg, st, datetime.now()); st.save()
print('sent =', len(res.sent), 'failed =', res.failed)
PY
check "after recovery everything is delivered" "0" "$(in_backup python3 -c "
from dbbackup.config import Config; from dbbackup.state import State; from dbbackup import transfer
cfg=Config.from_env(); print(len(transfer.pending(cfg, State(cfg.state_dir/'state.json'))))")"
INCOMING="$(docker exec e2e-secondary ls /home/dbbackup/incoming)"
check "two dumps now on the secondary" "2" "$(grep -c '\.sql\.gz\.age$' <<<"$INCOMING")"

# ------------------------------------------------------------------------------------------------
step "The restricted account can only upload: no shell, no listing, no reading back"
KEY="$(W "$PROJ/docker/secrets")/backup_ssh_key"
KH="$(W "$PROJ/docker/secrets")/backup_known_hosts"
chmod 600 "$KEY" 2>/dev/null || true
run_ssh() { docker run --rm --network e2ebk_default -v "$KEY":/k_src:ro -v "$KH":/kh:ro booking-backup \
              sh -c 'cp /k_src /k && chmod 600 /k && '"$1"; }
SHELLTRY="$(run_ssh 'ssh -i /k -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/kh dbbackup@secondary "id; ls /" 2>&1 || true')"
absent "arbitrary command is NOT executed" "uid=" "$SHELLTRY"
PULL="$(run_ssh 'mkdir -p /tmp/p && rsync -e "ssh -i /k -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/kh" dbbackup@secondary:/ /tmp/p/ 2>&1; ls /tmp/p | wc -l')"
check "cannot download the backups back (write-only)" "0" "$(tail -1 <<<"$PULL")"
WRONGKEY="$(docker run --rm --network e2ebk_default -v "$KH":/kh:ro booking-backup sh -c \
  'ssh-keygen -q -t ed25519 -N "" -f /tmp/other && ssh -i /tmp/other -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/kh dbbackup@secondary true 2>&1 || true')"
contains "an unknown key is rejected" "Permission denied" "$WRONGKEY"

# ------------------------------------------------------------------------------------------------
step "Retention on the secondary (prune.py runs there, keeping the newest N dumps)"
for n in 1 2; do
  in_backup python3 -c "
from datetime import datetime, timedelta
from dbbackup.config import Config; from dbbackup.state import State; from dbbackup import dump, transfer
cfg=Config.from_env(); st=State(cfg.state_dir/'state.json'); now=datetime.now()+timedelta(minutes=$n)
dump.make_dump(cfg, now); transfer.send_pending(cfg, st, now); st.save()" >/dev/null
done
BEFORE="$(docker exec e2e-secondary sh -c 'ls /home/dbbackup/incoming | grep -c "\.sql\.gz\.age$"')"
docker cp "$(W "$PROJ/dbbackup")/prune.py" e2e-secondary:/tmp/prune.py >/dev/null 2>&1 || true
docker exec e2e-secondary sh -c 'mkdir -p /tmp/dbb/dbbackup && cp /tmp/prune.py /tmp/dbb/dbbackup/prune.py && touch /tmp/dbb/dbbackup/__init__.py && cd /tmp/dbb && python3 -m dbbackup.prune --dir /home/dbbackup/incoming --keep-dumps 3'
AFTER="$(docker exec e2e-secondary sh -c 'ls /home/dbbackup/incoming | grep -c "\.sql\.gz\.age$"')"
echo "    dumps on secondary: before=$BEFORE after=$AFTER"
check "secondary keeps exactly the newest 3 dumps" "3" "$AFTER"
check "every kept dump still has its meta" "3" "$(docker exec e2e-secondary sh -c 'ls /home/dbbackup/incoming | grep -c "meta.json$"')"

# ------------------------------------------------------------------------------------------------
step "promote-secondary.sh: new database from the latest backup (encrypted, via the private age key)"
# A booking made AFTER the newest dump: it only exists in the binlog, so promotion must replay it.
sql "INSERT INTO booking (id, client_name, status_id) VALUES (9,'ines',2);" >/dev/null
in_backup python3 - <<'PY'
from datetime import datetime
from dbbackup.config import Config
from dbbackup.state import State
from dbbackup import binlogs, transfer
cfg = Config.from_env(); st = State(cfg.state_dir / 'state.json')
binlogs.flush_binary_logs(cfg)
print('archived:', binlogs.archive_new_binlogs(cfg, st))
res = transfer.send_pending(cfg, st, datetime.now()); st.save()
print('sent:', len(res.sent), 'failed:', res.failed)
PY
rm -rf "$WORK/incoming"; mkdir -p "$WORK/incoming"
docker cp e2e-secondary:/home/dbbackup/incoming/. "$(W "$WORK/incoming")/"
(cd "$PROJ" && ./scripts/promote-secondary.sh --backups-dir "$WORK/incoming" --plan-only) | sed 's/^/    /'
PROMOTE="$(cd "$PROJ" && ./scripts/promote-secondary.sh --age-key "$WORK/age_key.txt" --backups-dir "$WORK/incoming" \
            --env-file db/.env --network e2ebk_default --name e2e-promoted --yes 2>&1)"   || { fail "promote-secondary.sh failed"; echo "$PROMOTE" | tail -30 | sed 's/^/    | /'; }
echo "$PROMOTE" | sed -n '/=== Verification/,/=== Database restored/p' | sed 's/^/    /'
contains "plan includes the archived binlog" "1 file(s) to roll forward" "$PROMOTE"
contains "promotion finished" 'Database restored in container "e2e-promoted"' "$PROMOTE"
PROM() { docker exec e2e-promoted sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" bbdd -N -B -e "$1"' sh "$1" 2>/dev/null; }
check "promoted DB = newest dump + replayed binlog (booking 9 only exists in the binlog)" "1,2,3,4,5,6,7,8,9" "$(PROM 'SELECT GROUP_CONCAT(id ORDER BY id) FROM booking')"
check "promoted DB has the services too" "$(sql 'SELECT COUNT(*) FROM service_booking')" "$(PROM 'SELECT COUNT(*) FROM service_booking')"
check "app user can log in on the promoted DB" "9" "$(docker exec e2e-promoted sh -c 'mysql -uapp -papppw_e2e bbdd -N -B -e "SELECT COUNT(*) FROM booking"' 2>/dev/null)"
check "promoted DB keeps its own binlog for future recovery" "ON" "$(PROM 'SELECT @@log_bin' | sed 's/^1$/ON/')"
REFUSE="$(cd "$PROJ" && ./scripts/promote-secondary.sh --age-key "$WORK/age_key.txt" --backups-dir "$WORK/incoming" --env-file db/.env --network e2ebk_default --name e2e-promoted --yes 2>&1 || true)"
contains "refuses to run twice over an existing promoted DB" "already exists" "$REFUSE"
WRONG="$(docker run --rm booking-backup age-keygen 2>/dev/null)"
printf '%s\n' "$WRONG" > "$WORK/wrong_key.txt"
docker rm -f e2e-promoted >/dev/null; docker volume rm -f e2e-promoted-data >/dev/null
BADKEY="$(cd "$PROJ" && ./scripts/promote-secondary.sh --age-key "$WORK/wrong_key.txt" --backups-dir "$WORK/incoming" --env-file db/.env --network e2ebk_default --name e2e-promoted --yes 2>&1 || true)"
contains "a wrong private key cannot decrypt the backup" "no identity matched" "$BADKEY"

# ------------------------------------------------------------------------------------------------
echo
if [ "$FAILS" -eq 0 ]; then echo "${c_ok}ALL E2E CHECKS PASSED${c_off}"; else echo "${c_bad}$FAILS E2E CHECK(S) FAILED${c_off}"; fi
exit "$FAILS"
