# CI Pipeline

## Purpose

The GitHub Actions configuration provides bounded verification for the existing application. It does not deploy, publish releases, or use production infrastructure.

## Workflows And Triggers

`.github/workflows/ci.yml` runs:

- `backend-quality` with a 15-minute timeout;
- `postgres-concurrency` with a 20-minute timeout;
- `frontend-quality` with a 15-minute timeout;
- `compose-validation` with a 25-minute timeout.

`.github/workflows/e2e.yml` runs `e2e-smoke` with a 30-minute timeout.

Both workflows run on pull requests, pushes to `main`, and manual dispatch. There is no scheduled E2E run. New commits cancel superseded branch or pull-request runs, while manually dispatched investigations are not cancelled automatically.

Repository permissions are limited to `contents: read`.

## Job Responsibilities

### Backend Quality

- installs `backend/requirements-dev.txt` with Python 3.12 and pip caching;
- runs the complete backend suite with PostgreSQL-only tests intentionally skipped because no concurrency URL is set;
- compiles `app` and `tests`;
- verifies exactly one Alembic head and prints migration history;
- runs `pip-audit` without suppressing findings.

Warnings remain visible and test/audit failures fail the job.

### PostgreSQL Concurrency

- starts PostgreSQL 16 Alpine as a disposable service container;
- uses a database whose name explicitly identifies it as concurrency-only;
- migrates the fresh database to the dynamic Alembic head;
- compares `alembic current` with `alembic heads`;
- runs every test marked `postgres_concurrency`;
- parses JUnit XML to require at least one executed test and zero skips.

The committed database password and JWT value are clearly synthetic CI-only values. They are not accepted as production configuration.

### Frontend Quality

- uses Node 22 and npm caching from `frontend/package-lock.json`;
- runs `npm ci`, unit/component tests, and the production build;
- runs `npm audit`, `npm audit --omit=dev`, and `npm audit --omit=optional`;
- never runs an automatic force fix.

### Compose And Image Validation

- validates local Compose, scheduler, monitoring, production, and production scheduler configurations;
- builds the backend and frontend images once;
- builds the distinct production TLS proxy image;
- does not start production services or read production secret files.

### E2E Smoke

- installs only Playwright Chromium and its Linux runtime dependencies;
- calls `scripts/run_e2e_smoke.sh`;
- generates database, JWT, admin, and user credentials in process memory without shell tracing;
- builds and starts disposable PostgreSQL/backend/frontend services;
- migrates through Alembic head and seeds the disposable admin;
- executes the same six serial browser flows as local Task 63 verification;
- captures redacted status and bounded service logs on failure;
- always removes disposable containers, network, and PostgreSQL volume;
- verifies cleanup after the lifecycle script exits.

The serial browser contract contains exactly six flows:

1. Admin creates a disposable team, users, and an owned parking spot.
2. The parking owner sees the assigned spot automatically, confirms no raw Parking spot ID input is present, and publishes availability.
3. Employees apply and the scheduled assignment selects Employee A.
4. Admin validates and performs Applicant ID replacement.
5. Employees and admin see the replacement across operational pages.
6. Protected routes, role navigation, Help navigation, sidebar states, and the mobile Admin Overrides layout remain usable.

Static CI configuration tests guard the six-flow count and the owner-scoped/Help assertions so future UI changes cannot silently weaken the hosted E2E contract.

The Linux runner defaults to Compose project `parkingappe2eci`; the Windows runner remains `parkingappe2e`.

## Artifact Policy

Artifacts are uploaded only after failure and retained for five days.

- PostgreSQL concurrency: JUnit XML.
- E2E: HTML report, failure screenshots, last-run metadata, Docker status, and redacted service logs.

CI disables Playwright traces and videos because browser traces can contain entered passwords, request headers, or tokens. Local traces/videos remain available on failure and are gitignored. No database dump, environment file, production secret file, password, JWT, or bearer token should be uploaded.

Artifact upload uses `continue-on-error` so an upload problem cannot hide the original test failure.

## Local Reproduction

Backend quality from `backend`:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
python -m compileall -q app tests
python -m alembic -c alembic.ini heads
python -m alembic -c alembic.ini history
python -m pip_audit -r requirements-dev.txt
```

Frontend quality from `frontend`:

```powershell
npm.cmd ci
npm.cmd test
npm.cmd run build
npm.cmd audit
npm.cmd audit --omit=dev
npm.cmd audit --omit=optional
```

Compose validation from the repository root:

```powershell
docker-compose config --quiet
docker-compose --profile scheduler config --quiet
docker-compose --profile monitoring config --quiet
docker-compose -f docker-compose.production.yml config --quiet
docker-compose -f docker-compose.production.yml --profile scheduler config --quiet
```

Windows E2E:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_e2e_smoke.ps1
```

Linux E2E after `npm ci` and `npx playwright install --with-deps chromium` in `frontend`:

```bash
bash scripts/run_e2e_smoke.sh
```

PostgreSQL concurrency requires a disposable PostgreSQL database and `POSTGRES_CONCURRENCY_DATABASE_URL`; see `resources/docs/postgres_concurrency_load_validation.md` for the established local procedure.

## Troubleshooting

- If backend concurrency tests skip, confirm `POSTGRES_CONCURRENCY_DATABASE_URL` is set and the database name contains `concurrency`, `test`, `tmp`, `temporary`, or `disposable`.
- If Alembic validation fails, compare `alembic heads`, `alembic history`, and `alembic current` before changing migrations.
- If E2E startup fails, inspect the uploaded sanitized `docker-status.txt` and `service-logs.txt` plus the Playwright HTML report.
- If cleanup validation fails, remove only the disposable `parkingappe2eci` project; do not delete normal development volumes.
- If a dependency audit fails, update or explicitly assess the dependency. Do not suppress or force-fix the finding in CI.

## Hosted Verification Limitation

Workflow YAML and individual commands can be validated locally, but a definitive GitHub-hosted result requires committing `.github/workflows/ci.yml` and `.github/workflows/e2e.yml` to the actual repository and running GitHub Actions. This task does not initialize Git metadata, push branches, or publish anything.
