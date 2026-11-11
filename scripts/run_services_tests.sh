#!/usr/bin/env bash
# Starts the throw-away MariaDB + Redis (docker/docker-compose.test.yml), runs the real-services tests and always
# removes the containers and volumes afterwards. Run it from an activated Python virtual environment: it uses
# whatever `python` is on the PATH.
#
#   scripts/run_services_tests.sh                       # all services tests
#   scripts/run_services_tests.sh -k redis -x           # extra arguments go straight to pytest
#   scripts/run_services_tests.sh -m "services and not resilience"
#
# Exit code: pytest's (or 1 if the containers could not be started).
set -u

cd "$(dirname "${BASH_SOURCE[0]}")/.."
COMPOSE=(docker compose -f docker/docker-compose.test.yml)

cleanup() {
  echo "==> Removing test containers and volumes"
  "${COMPOSE[@]}" down -v --remove-orphans
}
trap cleanup EXIT

echo "==> Starting test containers (MariaDB, Redis)"
"${COMPOSE[@]}" up -d --wait || { echo "Could not start the test containers" >&2; exit 1; }

echo "==> Running services tests with $(command -v python)"
RUN_INTEGRATION_TESTS=1 python -m pytest tests/integration/services -m services -v "$@"
