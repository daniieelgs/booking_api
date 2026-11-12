#!/usr/bin/env bash
# Post-deploy smoke test: is the API up, is Redis reachable from it, is the expected version running and
# is the Celery worker alive? Exit code 0 = healthy, 1 = something is wrong (usable by CI/CD for rollback).
#
#   scripts/smoke_test.sh [--url https://booking-api.es] [--expect-version 1.1.0] [--worker docker-worker-1] [--sudo]
#
# --worker runs `celery inspect ping` inside that container (needs docker access; add --sudo on the primary).
set -u

URL="http://localhost:5000"
EXPECT_VERSION=""
WORKER=""
SUDO=""

while [ $# -gt 0 ]; do
  case "$1" in
    --url) URL="${2%/}"; shift 2 ;;
    --expect-version) EXPECT_VERSION="$2"; shift 2 ;;
    --worker) WORKER="$2"; shift 2 ;;
    --sudo) SUDO="sudo"; shift ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

FAILED=0
ok()   { echo "  ok   $*"; }
fail() { echo "  FAIL $*"; FAILED=1; }

fetch() { curl -fsS --max-time 10 "$1" 2>&1; }

echo "Smoke test against $URL"

HEALTH="$(fetch "$URL/health")" || { fail "GET /health unreachable: $HEALTH"; HEALTH=""; }
if [ -n "$HEALTH" ]; then
  case "$HEALTH" in
    *'"status"'*'"ok"'*) ok "/health status ok (database, redis and worker)" ;;
    *) fail "/health not ok: $HEALTH" ;;
  esac
fi

VERSION_JSON="$(fetch "$URL/version")" || { fail "GET /version unreachable: $VERSION_JSON"; VERSION_JSON=""; }
if [ -n "$VERSION_JSON" ]; then
  ok "/version $VERSION_JSON"
  if [ -n "$EXPECT_VERSION" ]; then
    case "$VERSION_JSON" in
      *"\"$EXPECT_VERSION\""*) ok "version is $EXPECT_VERSION" ;;
      *) fail "expected version $EXPECT_VERSION, got $VERSION_JSON" ;;
    esac
  fi
fi

if [ -n "$WORKER" ]; then
  if $SUDO docker exec "$WORKER" celery -A make_celery.celery inspect ping --timeout 10 2>&1 | grep -q "pong"; then
    ok "celery worker $WORKER answers ping"
  else
    fail "celery worker $WORKER did not answer ping"
  fi
fi

if [ "$FAILED" -eq 0 ]; then echo "SMOKE TEST PASSED"; else echo "SMOKE TEST FAILED"; fi
exit "$FAILED"
