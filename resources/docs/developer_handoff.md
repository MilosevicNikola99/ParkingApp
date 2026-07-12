# Developer Handoff

## Current Status

The application has an MVP backend, Vue frontend, local Docker Compose setup, PostgreSQL migrations through Alembic, local admin seeding, and smoke verification coverage. The current migration head is expected to be `0010`.

This document summarizes the architecture, implemented workflows, operational commands, and remaining limitations for the next developer.

## Architecture Overview

Backend code is organized around separated FastAPI routers, services, repositories, models, schemas, database configuration, security utilities, and command modules.

- `backend/app/main.py`: FastAPI application setup, middleware, CORS, security headers, and router registration.
- `backend/app/api/routes`: API routers for auth, health, parking workflows, admin workflows, overrides, audit logs, and reports.
- `backend/app/api/dependencies`: authentication and authorization dependencies, including current-user and role checks.
- `backend/app/services`: business behavior for authentication, parking availability, applications, reservations, assignment, ranking, overrides, audit logging, reports, and seeding support.
- `backend/app/repositories`: database-focused access layer.
- `backend/app/models`: SQLAlchemy models and enums.
- `backend/app/schemas`: Pydantic request and response schemas.
- `backend/app/core`: settings, JWT/password helpers, logging, and request context support.
- `backend/app/commands`: operational commands such as due assignment processing and safe local admin seeding.
- `backend/alembic`: migration environment and versioned migrations.

Frontend code follows a Vue/Vite structure.

- `frontend/src/router`: route definitions and auth-aware navigation behavior, including the authenticated `/help` route.
- `frontend/src/views`: login, dashboard, employee, parking owner, admin screens, and the static role-based Help page.
- `frontend/src/services`: API client modules for backend communication.
- `frontend/src/components`: reusable UI pieces. `AppLayout` owns the collapsible sidebar state through `localStorage` key `parking-app-sidebar-collapsed`.
- `frontend/nginx.conf`: static serving and Vue Router history fallback for Docker Compose.

## Implemented Domain Workflows

- Users and teams: admins can manage users and teams. Users have role-based access through `ADMIN`, `EMPLOYEE`, and `PARKING_OWNER`.
- Authentication: login returns JWT bearer tokens; `/auth/me` returns the active current user; invalid, expired, inactive, or missing-user tokens return 401.
- Authorization: reusable role dependencies return 403 for authenticated users without required roles.
- Parking spots: admin-managed spot records with ownership support. Authenticated users can call GET /parking-spots/mine to retrieve only their own active spots; users without owned active spots receive an empty list.
- Availabilities: parking owners can publish and cancel availability windows. The owner UI auto-selects one owned active spot or offers an owner-scoped selector for multiple spots. Server-side ownership, active-status, and overlap rules remain authoritative.
- Applications: employees can apply for open availability windows, view their applications, and cancel pending applications. Duplicate and owner self-application cases are guarded.
- Reservations: assignment creates reservations; employees can view and cancel their own active reservations.
- Assignment: due availability assignment uses service-layer transaction boundaries, candidate ranking, and audit logging.
- Overrides: admins can manually assign, replace, and cancel reservations while preserving audit trail data. Replacement can use an existing pending `application_id` or an `applicant_id`; the applicant path is admin-only and creates or reactivates the replacement application internally.
- Reports: admin report endpoints expose summary, top users, spot usage, audit activity, and CSV exports.

## Assignment Policy

The current ranking policy is centralized in `ParkingApplicationRankingService`.

- Same-team applicants rank first while `now <= priority_until`.
- `priority_until = None` disables same-team priority.
- Recent reservation wins are considered through the configured fairness window and soft limit.
- Final deterministic ordering uses `created_at`, then `id`.

Relevant settings include:

- `SAME_TEAM_PRIORITY_WINDOW_HOURS`
- `RECENT_WIN_FAIRNESS_WINDOW_DAYS`
- `RECENT_WIN_SOFT_LIMIT`

Keep future fairness changes at the ranking service boundary instead of spreading ranking logic through repositories or routers.

## Security Notes

- JWT settings live in backend configuration and must come from environment variables outside local development.
- Passwords are hashed through the shared security utility and are never returned by read schemas.
- CORS is configurable and defaults to local frontend origins.
- Security headers and request ID middleware are enabled for API responses.
- The local admin seed command refuses production-like environments and is disabled by default.
- Do not log plain-text passwords, JWTs, or seed secrets.

## Operational Commands

Start local Compose services:

```powershell
docker-compose build backend frontend
docker-compose up -d db backend frontend
docker-compose exec -T backend alembic -c alembic.ini upgrade head
```

Seed a local admin only in local/dev/test:

```powershell
$env:SEED_ADMIN_ENABLED = "true"
$env:SEED_ADMIN_EMAIL = "local.admin@example.com"
$env:SEED_ADMIN_USERNAME = "local_admin"
$env:SEED_ADMIN_PASSWORD = Read-Host "Local admin password"
docker-compose exec -T backend python -m app.commands.seed_admin
```

Run assignment processing:

```powershell
docker-compose exec -T backend python -m app.commands.assign_due_availabilities --limit 100
```

Run smoke checks:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke_test.ps1
```

Run backend regression checks:

```powershell
cd backend
python -m pytest
python -m compileall app tests
python -m alembic -c alembic.ini heads
python -m alembic -c alembic.ini history
```

Run frontend regression checks:

```powershell
cd frontend
npm test
npm run build
npm audit --omit=optional
```

Run the disposable frontend E2E smoke suite from the repository root:

```powershell
cd frontend
npx.cmd playwright install chromium
cd ..
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_e2e_smoke.ps1
```

The suite is intentionally serial because later replacement and audit assertions depend on records created by earlier browser steps. Accessible labels, roles, headings, and named regions are the selector contract. The lifecycle runner generates credentials in memory, uses Compose project `parkingappe2e` by default, sets the priority window to zero for deterministic one-shot assignment, and removes its PostgreSQL volume after the run. Playwright traces, videos, and screenshots are retained only for failures and are gitignored.

## Continuous Integration

- `.github/workflows/ci.yml` owns backend quality, PostgreSQL concurrency, frontend quality, Compose/profile validation, and bounded image builds.
- `.github/workflows/e2e.yml` owns the Linux Docker/Chromium six-flow MVP smoke suite.
- Python is `3.12`, Node is `22`, and PostgreSQL is `16-alpine`, matching project runtime expectations.
- CI uses only synthetic disposable credentials and read-only repository permissions.
- E2E traces/videos are disabled in CI to avoid credential-bearing artifacts; failure screenshots, HTML report, JUnit XML, and redacted service logs use five-day retention.
- Windows developers continue to use `scripts/run_e2e_smoke.ps1`; Linux/CI uses `scripts/run_e2e_smoke.sh`.
- Hosted verification requires committing the workflow files into the actual GitHub repository. Do not initialize or publish from a metadata-free workspace solely to run CI.
- Linux runners expose PowerShell as `pwsh`, while Windows uses `powershell.exe`; test helpers must resolve either executable.
- Concurrency JUnit validation must aggregate nested `<testsuite>` counters generated by pytest.

See `resources/docs/ci_pipeline.md` for local parity commands and troubleshooting.

## User-Facing Documentation

- `resources/docs/user_guide.md` is the end-user guide for employees, parking owners, and administrators.
- The in-app Help page provides short role-specific quick-start guidance for authenticated users without exposing internal file paths.
- `scripts/generate_user_guide_screenshots.ps1 -ConfirmOverwrite` regenerates the guide screenshots from disposable local data and removes its isolated Docker resources by default.

## Extension Points

- Add production-grade scheduler orchestration for assignment processing.
- Add SSO/OIDC if enterprise identity integration is required.
- Add notification/email delivery for assignments, cancellations, and admin overrides.
- Add production observability, metrics, alerting, tracing, and log shipping.
- Add backup/restore runbooks and managed secret storage for deployment environments.
- Extend the Playwright smoke suite only when completed MVP workflows change.
- Perform production-like PostgreSQL concurrency and load testing for assignment and override paths.
- Re-run full browser release-candidate QA after replacement override UI verification, including responsive layout screenshots.

## Known Limitations

- The Docker Compose stack is for local validation, not production deployment.
- No SSO/OIDC, email notification, scheduled report delivery, or external observability is implemented.
- Local seed admin credentials must be provided by the operator and are not generated by the application.
- Playwright smoke coverage exists for the six-flow critical MVP path, including owner-scoped parking spot publishing without a raw ID input and authenticated Help navigation; exploratory manual QA is still required for broader rendering and usability review.
- If host port `8080` is occupied locally, the frontend Docker image can still be smoke-tested on an alternate host port, but the normal Compose configuration expects `http://localhost:8080`.
- Production readiness requires deployment-specific TLS, secrets, backups, monitoring, and concurrency validation.

See `resources/docs/manual_qa_checklist.md` for release-candidate manual testing and `resources/docs/implementation_log.md` for task-by-task verification history.
