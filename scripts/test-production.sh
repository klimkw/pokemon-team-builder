#!/usr/bin/env bash
# Exercise Render's image and startup command against an empty, disposable DB.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
project="${PRODUCTION_TEST_PROJECT:-pokemon-team-builder-tests-production}"
if [[ ! "$project" =~ ^pokemon-team-builder-tests-production(-[a-z0-9-]+)?$ ]]; then
  echo 'PRODUCTION_TEST_PROJECT must start with pokemon-team-builder-tests-production' >&2
  exit 2
fi
compose=(docker compose --env-file /dev/null --project-name "$project" --file compose.production-test.yaml)
mkdir -p test-artifacts/production
cleanup() {
  "${compose[@]}" logs --no-color > test-artifacts/production/containers.log 2>&1 || true
  "${compose[@]}" down --remove-orphans --volumes
}
trap cleanup EXIT
"${compose[@]}" build
"${compose[@]}" up -d --wait
# Test code is streamed in: neither fixtures nor test dependencies enter the image.
"${compose[@]}" exec -T app python - < scripts/production-smoke.py
