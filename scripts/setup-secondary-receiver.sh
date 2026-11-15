#!/usr/bin/env bash
# Prepares the SECONDARY server to RECEIVE the encrypted database backups from the primary.
# Run once, as root, on the secondary:
#
#   sudo ./scripts/setup-secondary-receiver.sh --pubkey /path/to/backup_ssh_key.pub [--reader daniieelgs]
#
# What it does (idempotent, safe to re-run; it touches nothing else on the machine):
#   1. creates the Linux account "dbbackup" (no password, no sudo, no docker group);
#   2. creates /home/dbbackup/incoming (where the primary drops files);
#   3. authorizes the primary's SSH key with  restrict,command="rrsync -wo <incoming>"  -> that key can ONLY
#      upload into that directory: no shell, no listing, no reading back, no port forwarding;
#   4. installs prune.py and a cron entry (/etc/cron.d/dbbackup-prune) that keeps the newest N dumps;
#   5. prints the host key fingerprint to verify when pinning known_hosts on the primary.
#
# Options:
#   --pubkey FILE     REQUIRED. Public half of the SSH key the primary will use (backup_ssh_key.pub).
#   --user NAME       account name (default dbbackup)
#   --keep-dumps N    dumps to keep (default 3)
#   --reader USER     also lets this existing user READ the incoming directory (needed to run
#                     promote-secondary.sh without sudo); takes effect after that user logs in again.
#   --dry-run         only show what would be done
set -euo pipefail

cd "$(dirname "$0")/.."

PUBKEY_FILE=""; ACCOUNT="dbbackup"; KEEP=3; READER=""; DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --pubkey)     PUBKEY_FILE="${2:-}"; shift 2 ;;
    --user)       ACCOUNT="${2:-}"; shift 2 ;;
    --keep-dumps) KEEP="${2:-}"; shift 2 ;;
    --reader)     READER="${2:-}"; shift 2 ;;
    --dry-run)    DRY=1; shift ;;
    -h|--help)    sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

[ "$(id -u)" -eq 0 ] || { echo "ERROR: run as root (sudo)" >&2; exit 1; }
[ -n "$PUBKEY_FILE" ] && [ -f "$PUBKEY_FILE" ] || { echo "ERROR: --pubkey FILE is required and must exist" >&2; exit 2; }
[[ "$ACCOUNT" =~ ^[a-z_][a-z0-9_-]*$ ]] || { echo "ERROR: invalid --user" >&2; exit 2; }
[[ "$KEEP" =~ ^[1-9][0-9]*$ ]] || { echo "ERROR: --keep-dumps must be a positive integer" >&2; exit 2; }
[ -f dbbackup/prune.py ] || { echo "ERROR: dbbackup/prune.py not found (run from the repository checkout)" >&2; exit 1; }
if [ -n "$READER" ]; then id "$READER" >/dev/null 2>&1 || { echo "ERROR: --reader user $READER does not exist" >&2; exit 2; }; fi

# Exactly one well-formed public key line; never accept options smuggled in the file (e.g. a "command=" prefix).
PUBKEY="$(grep -v '^[[:space:]]*#' "$PUBKEY_FILE" | sed '/^[[:space:]]*$/d')"
[ "$(printf '%s\n' "$PUBKEY" | wc -l)" -eq 1 ] || { echo "ERROR: $PUBKEY_FILE must contain exactly one public key" >&2; exit 2; }
[[ "$PUBKEY" =~ ^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp(256|384|521))\ [A-Za-z0-9+/=]+(\ .*)?$ ]] \
  || { echo "ERROR: $PUBKEY_FILE does not look like a plain SSH public key (must start with ssh-ed25519/ssh-rsa/ecdsa-...)" >&2; exit 2; }

command -v python3 >/dev/null || { echo "ERROR: python3 is required (retention script)" >&2; exit 1; }
command -v rsync   >/dev/null || { echo "ERROR: rsync is not installed (apt install rsync)" >&2; exit 1; }
[ -d /etc/cron.d ] || { echo "ERROR: /etc/cron.d not found: cron is not installed" >&2; exit 1; }

RRSYNC="$(command -v rrsync || true)"
[ -n "$RRSYNC" ] || { [ -x /usr/share/doc/rsync/scripts/rrsync ] && RRSYNC=/usr/share/doc/rsync/scripts/rrsync; }
[ -n "$RRSYNC" ] || { echo "ERROR: rrsync not found. It ships with the rsync package (/usr/bin/rrsync or /usr/share/doc/rsync/scripts/rrsync)." >&2; exit 1; }

HOME_DIR="/home/$ACCOUNT"
INCOMING="$HOME_DIR/incoming"

run() { if [ "$DRY" = 1 ]; then echo "  [dry-run] $*"; else "$@"; fi; }

echo "== Plan: account=$ACCOUNT incoming=$INCOMING rrsync=$RRSYNC keep=$KEEP dumps${READER:+ reader=$READER}"

# sshd restrictions that would silently lock the new account out
ALLOW="$(sshd -T 2>/dev/null | grep -iE '^(allowusers|allowgroups) ' || true)"
if [ -n "$ALLOW" ]; then
  echo "WARNING: sshd restricts logins ($ALLOW). Add '$ACCOUNT' to it or the primary will be refused."
fi
PUBAUTH="$(sshd -T 2>/dev/null | grep -i '^pubkeyauthentication ' || true)"
case "$PUBAUTH" in *no*) echo "WARNING: sshd has PubkeyAuthentication disabled; key logins will fail." ;; esac

# 1. account (no password; /bin/sh because sshd runs the forced command through the login shell)
if id "$ACCOUNT" >/dev/null 2>&1; then
  echo "== Account $ACCOUNT already exists"
else
  echo "== Creating account $ACCOUNT"
  run useradd -m -s /bin/sh "$ACCOUNT"
fi
run passwd -l "$ACCOUNT" >/dev/null

# 2. directories
run install -d -o "$ACCOUNT" -g "$ACCOUNT" -m 700 "$HOME_DIR/.ssh"
run install -d -o "$ACCOUNT" -g "$ACCOUNT" -m 750 "$INCOMING"

# 3. restricted key (the file is rewritten as a whole, so re-running replaces any previous key)
LINE="restrict,command=\"$RRSYNC -wo $INCOMING\" $PUBKEY"
echo "== Authorizing the key with a forced write-only rrsync"
if [ "$DRY" = 1 ]; then echo "  [dry-run] authorized_keys <- $LINE"; else
  printf '%s\n' "$LINE" > "$HOME_DIR/.ssh/authorized_keys"
  chown "$ACCOUNT:$ACCOUNT" "$HOME_DIR/.ssh/authorized_keys"
  chmod 600 "$HOME_DIR/.ssh/authorized_keys"
fi

# 4. retention
echo "== Installing retention (prune.py + /etc/cron.d/dbbackup-prune)"
run install -o "$ACCOUNT" -g "$ACCOUNT" -m 755 dbbackup/prune.py "$HOME_DIR/prune.py"
CRON_LINE="30 5 * * * $ACCOUNT python3 $HOME_DIR/prune.py --dir $INCOMING --keep-dumps $KEEP"
if [ "$DRY" = 1 ]; then echo "  [dry-run] cron.d <- $CRON_LINE"; else
  printf '# Retention of the database backups received from the primary (managed by setup-secondary-receiver.sh)\n%s\n' "$CRON_LINE" > /etc/cron.d/dbbackup-prune
  chmod 644 /etc/cron.d/dbbackup-prune
fi

# optional reader (so the owner can run promote-secondary.sh without sudo)
if [ -n "$READER" ]; then
  echo "== Letting $READER read $INCOMING (group $ACCOUNT, applies at next login)"
  run usermod -aG "$ACCOUNT" "$READER"
  run chmod 750 "$HOME_DIR"
fi

echo
echo "== Host key fingerprints of this server (verify them when pinning known_hosts on the primary):"
for f in /etc/ssh/ssh_host_ed25519_key.pub /etc/ssh/ssh_host_rsa_key.pub; do
  [ -f "$f" ] && ssh-keygen -lf "$f" | sed 's/^/   /'
done
echo
echo "Done. Next, on the primary: ssh-keyscan -t ed25519 <this host> > docker/secrets/backup_known_hosts"
echo "and compare the fingerprint above with: ssh-keygen -lf docker/secrets/backup_known_hosts"
echo "Check the restriction from the primary: ssh -i <key> $ACCOUNT@<this host> id   (must NOT print uid=...)"
