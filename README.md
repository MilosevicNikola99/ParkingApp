# Parking Management App

FastAPI and Vue application for managing employee parking availability, applications, reservations, assignment decisions, admin operations, and reporting.

## Release Status

- MVP release: `v1.0.0-mvp`
- Hosted CI: passing
- Alembic head: `0010`
- Local runtime: Docker Compose
- Production deployment: not included in the MVP release

## Stack

- Backend: Python, FastAPI, SQLAlchemy, Pydantic v2, Alembic, PostgreSQL, JWT authentication.
- Frontend: Vue 3, Vite, Vue Router, Axios, production static serving through nginx.
- Local infrastructure: Docker Compose services for PostgreSQL, backend, and frontend.

## Project Structure

- `backend/app`: FastAPI application, routers, services, repositories, schemas, models, commands, and configuration.
- `backend/alembic`: database migrations.
- `frontend/src`: Vue application, route views, reusable components, API services, and auth storage.
- `scripts`: local smoke and verification scripts.
- `resources/docs`: planning, implementation log, deployment/security notes, handoff, and QA docs.

Production operators should start with the [production deployment plan](resources/docs/production_deployment_plan.md) for architecture, prerequisites, deployment, rollback, backup, monitoring, and validation steps.

Before production, execute the [staging deployment rehearsal](resources/docs/staging_deployment_rehearsal.md) with synthetic secrets and data, and record the acceptance result.

## Local Docker Setup

Copy the example environment file before starting local services:

```powershell
Copy-Item .env.example .env
```

Build and start the application:

```powershell
docker-compose config
docker-compose build backend frontend
docker-compose up -d db backend frontend
docker-compose exec -T backend alembic -c alembic.ini upgrade head
```

Local URLs:

- Frontend: `http://localhost:8080`
- Backend API: `http://localhost:8000`
- OpenAPI docs: `http://localhost:8000/docs`
- PostgreSQL: `localhost:5432`

Some Docker installs use `docker compose` instead of `docker-compose`. Use the equivalent command form available on your machine.

## Local Admin Seed

The seed command is for local development and test environments only. It is disabled by default and refuses production-like environments.

Set local-only values, recreate the backend container if needed, and run the command:

```powershell
$env:SEED_ADMIN_ENABLED = "true"
$env:SEED_ADMIN_EMAIL = "local.admin@example.com"
$env:SEED_ADMIN_USERNAME = "local_admin"
$env:SEED_ADMIN_FIRST_NAME = "Local"
$env:SEED_ADMIN_LAST_NAME = "Admin"
$env:SEED_ADMIN_PASSWORD = Read-Host "Local admin password"

docker-compose up -d db backend frontend
docker-compose exec -T backend python -m app.commands.seed_admin
```

Do not commit real seed credentials. By default, existing admin passwords are not overwritten. Set `SEED_ADMIN_UPDATE_PASSWORD=true` only when intentionally rotating a local seed password.

## Smoke Testing

After migrations and an admin seed are available, run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke_test.ps1
```

The smoke script reads credentials from `SMOKE_TEST_USERNAME` and `SMOKE_TEST_PASSWORD`. It also supports the seed admin environment variables for local verification.

## Frontend End-To-End Smoke

Playwright covers the completed MVP browser flow with disposable Docker data. Install the pinned Chromium runtime once, then run the lifecycle script from the project root:

```powershell
cd frontend
npm.cmd install
npx.cmd playwright install chromium
cd ..
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_e2e_smoke.ps1
```

The script uses a dedicated Compose project, isolated host ports, generated credentials, Alembic head `0010`, and a disposable PostgreSQL volume. It builds and starts `db`, `backend`, and `frontend`, seeds a local-only admin, runs the browser suite and assignment command, then removes the containers and volume. Use `-KeepStack` only while diagnosing a local failure.

When a prepared disposable stack is already running, run Playwright directly from `frontend`:

```powershell
npm.cmd run e2e:smoke
npm.cmd run e2e:headed
npm.cmd run e2e:ui
```

Direct runs require `E2E_BASE_URL`, `E2E_ADMIN_USERNAME`, `E2E_ADMIN_PASSWORD`, `E2E_USER_PASSWORD`, and the matching `E2E_COMPOSE_PROJECT`. Test artifacts are written to `frontend/test-results` and `frontend/playwright-report`; both are gitignored and may contain local test credentials in traces. Inspect a trace with `npx.cmd playwright show-trace <trace.zip>` and remove artifacts after diagnosis.

## End-User Guide

The role-based browser guide is available at `resources/docs/user_guide.md`. Its screenshots are generated from disposable local data with:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\generate_user_guide_screenshots.ps1 -ConfirmOverwrite
```

The screenshot generator uses an isolated Docker Compose project, replaces only `resources/docs/images/user_guide/*.png` after a successful run, and removes its disposable containers and PostgreSQL volume by default.

## Continuous Integration

Repository-ready GitHub Actions workflows are in `.github/workflows`:

- `ci.yml`: backend tests/compile/Alembic/audit, PostgreSQL concurrency tests, frontend tests/build/audits, Compose validation, and bounded image builds.
- `e2e.yml`: the six-test Chromium MVP smoke suite against disposable Docker services.

Both workflows run for pull requests, pushes to `main`, and manual dispatch. Every job has a timeout, read-only repository permissions, and branch/PR concurrency cancellation. E2E failure reports, screenshots, and sanitized service logs are retained for five days; CI disables traces and videos because they may capture disposable credentials.

Local Windows parity uses the existing PowerShell lifecycle:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_e2e_smoke.ps1
```

Linux and hosted CI use:

```bash
bash scripts/run_e2e_smoke.sh
```

Full workflow responsibilities, reproduction commands, artifact handling, and troubleshooting are documented in `resources/docs/ci_pipeline.md`. Hosted execution requires these files to be committed to the real GitHub repository; this workspace is not initialized or published by the CI task.

## Swagger Authorization

OpenAPI docs are available at `http://localhost:8000/docs`.

Use the `Authorize` button with:

- `username`: your username or email.
- `password`: your password.
- `client_id`: leave empty.
- `client_secret`: leave empty.

The Swagger OAuth2 password modal posts form data to `/auth/token`. Application clients and the frontend can continue to use `/auth/login` with JSON:

```json
{
  "identifier": "local_admin",
  "password": "your-password"
}
```

## Backend Development

```powershell
cd backend
python -m pip install -r requirements.txt
python -m pytest
python -m compileall app tests
python -m alembic -c alembic.ini heads
python -m alembic -c alembic.ini history
```

Common migration commands:

```powershell
python -m alembic -c alembic.ini revision --autogenerate -m "description"
python -m alembic -c alembic.ini upgrade head
python -m alembic -c alembic.ini downgrade -1
python -m alembic -c alembic.ini current
```

Run the assignment command locally through Docker:

```powershell
docker-compose exec -T backend python -m app.commands.assign_due_availabilities --limit 100
```

Run one protected scheduler cycle or start the optional scheduler service:

```powershell
docker-compose exec -T -e ASSIGNMENT_SCHEDULER_ENABLED=true backend python -m app.commands.run_assignment_scheduler --once
docker-compose --profile scheduler up -d assignment-scheduler
```

Scheduler configuration and operational notes are in `resources/docs/assignment_scheduler.md`.

## Local Load Validation

Phase 3A provides a bounded backend API smoke profile. Phase 3B adds a confirmed moderate profile with Prometheus metric deltas, PostgreSQL aggregate diagnostics, and a bounded pool saturation/recovery diagnostic.

```powershell
$env:LOAD_VALIDATION_ADMIN_IDENTIFIER = "local_admin"
$env:LOAD_VALIDATION_ADMIN_PASSWORD = Read-Host "Load validation admin password"

docker-compose exec -T backend python -m app.commands.run_load_validation --profile smoke --target-base-url http://localhost:8000 --report-path /tmp/load-validation-smoke.json
```

Run the moderate profile only against disposable local data:

```powershell
docker-compose --profile monitoring up -d assignment-scheduler prometheus

docker-compose exec -T backend python -m app.commands.run_load_validation `
  --profile moderate `
  --confirm-moderate `
  --target-base-url http://localhost:8000 `
  --scheduler-metrics-url http://assignment-scheduler:9101/metrics `
  --concurrency 25 `
  --iterations 1 `
  --request-timeout 15 `
  --global-timeout 240 `
  --report-path /tmp/load-validation-moderate.json `
  --markdown-report-path /tmp/load-validation-moderate.md
```

The smoke and moderate profiles create disposable users, teams, parking spots, availabilities, applications, reservations, cancellations, reassignment, admin override, replacement override, and report reads. Cleanup is enabled by default. The command refuses non-local API targets unless `--allow-non-local-target` is explicitly set. These profiles are local validation checks, not production capacity benchmarks.

Configuration and report details are in `resources/docs/postgres_concurrency_load_validation.md`.

## Monitoring

Operational health and Prometheus metrics are available at:

- `GET /health/live`
- `GET /health/ready`
- `GET /metrics`

Start the local monitoring profile:

```powershell
docker-compose --profile monitoring up -d assignment-scheduler prometheus grafana
```

Prometheus is available at `http://127.0.0.1:9090`; Grafana is available at `http://127.0.0.1:3000` with local-only defaults from `.env.example`. Full guidance is in `resources/docs/monitoring_observability.md`.

## PostgreSQL Backup And Restore

Backup and restore scripts are available for Docker Compose based operations:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\backup_postgres.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify_postgres_backup.ps1 -BackupFile .\backups\postgres\<backup>.pgdump
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\restore_postgres.ps1 -BackupFile .\backups\postgres\<backup>.pgdump -TargetDatabase parking_app_restore_verify
```

Backups are PostgreSQL custom-format archives with checksum metadata. Full operational guidance is in `resources/docs/postgres_backup_restore.md`.

## Production Secrets And TLS Groundwork

Production-oriented secrets/TLS configuration is documented in `resources/docs/production_secrets_tls.md`.

The project includes `docker-compose.production.yml` as deployment groundwork with:

- file-based Docker secrets for JWT, PostgreSQL password, TLS certificate, and TLS private key,
- an internal-only backend service,
- an nginx TLS proxy serving the Vue frontend and proxying `/api/` to FastAPI,
- HTTP-to-HTTPS redirect,
- no committed real secrets or certificates.

Generate a disposable local self-signed certificate for verification:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\generate_local_tls_certificate.ps1
```

## Frontend Development

```powershell
cd frontend
npm ci
npm test
npm run build
npm audit --omit=optional
```

The frontend expects `VITE_API_BASE_URL` to point to the browser-visible backend URL. For local Compose, that value is `http://localhost:8000`.

## Stopping Services

Preserve local PostgreSQL data:

```powershell
docker-compose down
```

Remove local PostgreSQL data:

```powershell
docker-compose down -v
```

## Known Limitations

- SSO/OIDC, email notifications, scheduled reports, and external observability integrations are not implemented.
- The normal local Compose setup is not production infrastructure. Production-oriented secrets/TLS groundwork is provided separately in `docker-compose.production.yml`.
- The admin seed command is intentionally local/dev/test only and should remain disabled in production-like environments.
- Manual browser QA is still required before a real release, especially for responsive layout, admin workflows, and end-to-end role behavior.
- Phase 3A smoke and Phase 3B moderate load validation are available for local disposable checks. Stress profiles, distributed load testing, and production-like PostgreSQL capacity validation remain future hardening work.

Additional release and handoff details are in `resources/docs/developer_handoff.md` and `resources/docs/manual_qa_checklist.md`.
