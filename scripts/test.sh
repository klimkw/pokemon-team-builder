#!/usr/bin/env bash
# One disposable stack; development credentials and volumes are never used.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
project="${TEST_COMPOSE_PROJECT:-pokemon-team-builder-tests}"
if [[ ! "$project" =~ ^pokemon-team-builder-tests(-[a-z0-9-]+)?$ ]]; then
  echo 'TEST_COMPOSE_PROJECT must start with pokemon-team-builder-tests' >&2
  exit 2
fi
export TEST_APP_ORIGIN=http://frontend-test
export TEST_DB_PORT=0 TEST_FRONTEND_PORT=0
compose=(docker compose --env-file /dev/null --project-name "$project" --file compose.test.yaml)
mkdir -p test-artifacts
# Containers own their report subdirectories; keep repeated host runs writable.
chmod a+rwx test-artifacts
cleanup() { "${compose[@]}" down --remove-orphans; }
trap cleanup EXIT
"${compose[@]}" build
"${compose[@]}" up -d --wait db-test api-test frontend-test scanner-test
status=0
# Run all layers even if one fails, then return a failing status to CI.
"${compose[@]}" run --rm --no-deps backend-tests python -m pytest -q || status=1
"${compose[@]}" run --rm --no-deps backend-tests python -m pytest --postgres -q \
  --cov=app --cov-branch --cov-report=term-missing \
  --cov-report=xml:/artifacts/backend/coverage.xml \
  --cov-report=json:/artifacts/backend/coverage.json \
  --cov-report=html:/artifacts/backend/html || status=1
"${compose[@]}" run --rm --no-deps frontend-tests npm run test:coverage -- --maxWorkers=1 \
  --coverage.reportsDirectory=/artifacts/frontend || status=1
if "${compose[@]}" run --rm --no-deps catalog-fixture; then
  "${compose[@]}" run --rm --no-deps e2e || status=1
else
  status=1
fi
exit "$status"
