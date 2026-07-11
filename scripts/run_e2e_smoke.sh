#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
frontend_root="$repo_root/frontend"
compose_project="${E2E_COMPOSE_PROJECT:-parkingappe2eci}"

if [[ ! "$compose_project" =~ ^[A-Za-z0-9][A-Za-z0-9_-]*$ ]]; then
  printf 'E2E_COMPOSE_PROJECT contains unsupported characters.\n' >&2
  exit 2
fi

command -v docker >/dev/null
command -v openssl >/dev/null

run_id="$(date -u +%Y%m%d%H%M%S)"
admin_password="E2E-Admin-$(openssl rand -hex 20)-Aa1!"
user_password="E2E-User-$(openssl rand -hex 20)-Aa1!"
database_password="$(openssl rand -hex 24)"
jwt_secret="$(openssl rand -hex 32)"

export ENVIRONMENT="test"
export POSTGRES_DB="parking_app_e2e"
export POSTGRES_USER="parking_app_e2e"
export POSTGRES_PASSWORD="$database_password"
export POSTGRES_PORT="55435"
export BACKEND_PORT="18003"
export FRONTEND_PORT="18083"
export VITE_API_BASE_URL="http://localhost:18003"
export CORS_ALLOWED_ORIGINS='["http://localhost:18083"]'
export JWT_SECRET_KEY="$jwt_secret"
export SAME_TEAM_PRIORITY_WINDOW_HOURS="0"
export SEED_ADMIN_ENABLED="true"
export SEED_ADMIN_EMAIL="e2e.admin.${run_id}@example.com"
export SEED_ADMIN_USERNAME="e2e_admin_${run_id}"
export SEED_ADMIN_FIRST_NAME="E2E"
export SEED_ADMIN_LAST_NAME="Admin"
export SEED_ADMIN_PASSWORD="$admin_password"
export SEED_ADMIN_UPDATE_PASSWORD="true"
export E2E_COMPOSE_PROJECT="$compose_project"
export E2E_COMPOSE_COMMAND="${E2E_COMPOSE_COMMAND:-docker}"
export E2E_RUN_ID="$run_id"
export E2E_BASE_URL="http://localhost:18083"
export E2E_API_BASE_URL="http://localhost:18003"
export E2E_ADMIN_USERNAME="$SEED_ADMIN_USERNAME"
export E2E_ADMIN_PASSWORD="$admin_password"
export E2E_USER_PASSWORD="$user_password"

compose() {
  docker compose -p "$compose_project" "$@"
}

sanitize() {
  sed \
    -e "s|$admin_password|[REDACTED]|g" \
    -e "s|$user_password|[REDACTED]|g" \
    -e "s|$database_password|[REDACTED]|g" \
    -e "s|$jwt_secret|[REDACTED]|g"
}

capture_failure_diagnostics() {
  local artifact_dir="$frontend_root/test-results"
  mkdir -p "$artifact_dir"
  compose ps -a 2>&1 | sanitize | tee "$artifact_dir/docker-status.txt" || true
  compose logs --no-color --tail=300 db backend frontend 2>&1 \
    | sanitize \
    | tee "$artifact_dir/service-logs.txt" || true
}

cleanup() {
  local status=$?
  trap - EXIT
  set +e
  if [[ $status -ne 0 && "${E2E_CAPTURE_FAILURE_LOGS:-false}" == "true" ]]; then
    capture_failure_diagnostics
  fi
  compose down -v --remove-orphans
  exit "$status"
}
trap cleanup EXIT

wait_for_http() {
  local uri="$1"
  local attempts="${2:-40}"
  for ((attempt = 1; attempt <= attempts; attempt++)); do
    if curl --fail --silent --show-error --max-time 3 "$uri" >/dev/null; then
      return 0
    fi
    sleep 2
  done
  printf 'Timed out waiting for %s\n' "$uri" >&2
  return 1
}

cd "$repo_root"
printf "Preparing disposable E2E Docker project '%s'.\n" "$compose_project"
compose down -v --remove-orphans >/dev/null 2>&1 || true
compose config --quiet
compose build backend frontend
compose up -d db backend frontend
compose exec -T backend alembic -c alembic.ini upgrade head
compose exec -T backend alembic -c alembic.ini current
compose exec -T backend python -m app.commands.seed_admin

wait_for_http "http://localhost:18003/health"
wait_for_http "http://localhost:18083/"

cd "$frontend_root"
npm run e2e:smoke
