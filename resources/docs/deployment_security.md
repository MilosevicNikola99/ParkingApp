# Deployment and Security

This document describes the current MVP deployment and security baseline. It is not a substitute for an infrastructure-specific threat model or production runbook.

## Local Docker Compose

Copy `.env.example` to `.env` and replace development secrets when needed.

```powershell
docker-compose build
docker-compose up -d db backend frontend
docker-compose exec backend alembic -c alembic.ini upgrade head
```

Local endpoints:

- Frontend: `http://localhost:8080`
- Backend API and OpenAPI: `http://localhost:8000` and `http://localhost:8000/docs`
- Backend health: `http://localhost:8000/health`
- PostgreSQL: `localhost:5432`

Check health and stop services:

```powershell
Invoke-RestMethod http://localhost:8000/health
docker-compose ps
docker-compose down
```

`docker-compose down` preserves the named PostgreSQL volume. `docker-compose down -v` deletes the volume and all local database data.

### Final Local Verification Sequence

When Docker Desktop is available, use this sequence before release:

```powershell
docker-compose config
docker-compose build backend frontend
docker-compose up -d db backend frontend
docker-compose exec -T backend alembic -c alembic.ini upgrade head
.\scripts\smoke_test.ps1
docker-compose down
```

The smoke script checks backend health, frontend `/`, `/login`, and `/dashboard`, unauthenticated protected-route rejection, configured-origin CORS preflight, Alembic current/head state, and optional prepared-user authentication.

Authenticated smoke checks use the first complete credential pair found in this order:

1. `SMOKE_TEST_USERNAME` and `SMOKE_TEST_PASSWORD`
2. legacy `SMOKE_LOGIN_IDENTIFIER` and `SMOKE_LOGIN_PASSWORD`
3. `SEED_ADMIN_USERNAME` and `SEED_ADMIN_PASSWORD`

Set dedicated smoke credentials only for the current shell when an approved prepared user already exists:

```powershell
$env:SMOKE_TEST_USERNAME = "prepared-user-identifier"
$env:SMOKE_TEST_PASSWORD = Read-Host "Prepared user password"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke_test.ps1
Remove-Item Env:SMOKE_TEST_USERNAME, Env:SMOKE_TEST_PASSWORD
```

Do not place smoke credentials in the script, `.env`, command history, or source control. The current authenticated smoke checks are read-only.

## Production Secrets And TLS Groundwork

Detailed production secret and TLS guidance is in `resources/docs/production_secrets_tls.md`.

The backend now fails fast for unsafe production settings. When `ENVIRONMENT=production` or `ENVIRONMENT=prod`, startup rejects default/weak JWT secrets, example database passwords, enabled seed-admin behavior, debug logging, localhost or non-HTTPS CORS origins, and malformed/wildcard CORS origins.

Production-compatible secret files are supported for Docker secrets:

```text
JWT_SECRET_FILE=/run/secrets/jwt_secret
DATABASE_PASSWORD_FILE=/run/secrets/postgres_password
POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password
```

The production-oriented Compose file is `docker-compose.production.yml`. It keeps backend and PostgreSQL off host ports, serves the Vue frontend through an nginx TLS proxy, redirects HTTP to HTTPS, and proxies `/api/` to FastAPI. It expects these gitignored files or platform-equivalent secrets:

```text
secrets/jwt_secret.txt
secrets/postgres_password.txt
secrets/tls_certificate.pem
secrets/tls_private_key.pem
```

Production Compose uses `PRODUCTION_CORS_ALLOWED_ORIGINS` and `PRODUCTION_VITE_API_BASE_URL` so local `.env` values for browser-local development do not silently affect the TLS proxy configuration.

Generate a disposable local certificate for verification:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\generate_local_tls_certificate.ps1
```

The helper requires `openssl` on PATH. If OpenSSL is unavailable, generate equivalent localhost SAN certificate/key files manually in `secrets/`.

Production proxy notes:

- TLS protocols are limited to TLS 1.2 and TLS 1.3.
- HSTS is intentionally commented in the committed nginx config. Enable it only after HTTPS is verified for the real domain.
- The backend production command trusts forwarded headers only in the production Compose shape where the backend has no host-published port.
- Do not use `--proxy-headers` with broad trusted IPs if the backend is directly internet-exposed.

### Local Admin Seed Command

The import-safe `python -m app.commands.seed_admin` command creates or updates one local admin for development and smoke testing. It is not a production provisioning mechanism and does not expose a registration endpoint.

Safety behavior:

- `SEED_ADMIN_ENABLED` defaults to `false`; disabled execution exits successfully without opening a database session or changing data.
- Execution is allowed only when `ENVIRONMENT` is `local`, `development`, `dev`, or `test`. Production, staging, and other environments are refused even when enabled.
- Email, username, password, first name, and last name are all required when enabled and are validated through the existing user schema.
- The password uses the existing bcrypt helper and is never printed. Settings hold it as a redacted secret value.
- Matching existing users are updated to the configured profile, active state, and admin role.
- Existing passwords remain unchanged unless `SEED_ADMIN_UPDATE_PASSWORD=true`.
- If the configured email and username belong to different users, the command refuses to merge them.

Required local environment variables:

```text
SEED_ADMIN_ENABLED=true
SEED_ADMIN_EMAIL=local.admin@example.com
SEED_ADMIN_USERNAME=local_admin
SEED_ADMIN_PASSWORD=<local-only password>
SEED_ADMIN_FIRST_NAME=Local
SEED_ADMIN_LAST_NAME=Admin
SEED_ADMIN_UPDATE_PASSWORD=false
```

Set these values in the current shell before creating the backend container, then run:

```powershell
docker-compose up -d db backend frontend
docker-compose exec -T backend alembic -c alembic.ini upgrade head
docker-compose exec -T backend python -m app.commands.seed_admin
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke_test.ps1
docker-compose down
```

Remove seed variables from the shell after testing. Keep `SEED_ADMIN_ENABLED=false` in normal development and every deployed environment.

## Database Migrations and Assignment Scheduling

Apply migrations before starting a new application version:

```powershell
docker-compose exec backend alembic -c alembic.ini current
docker-compose exec backend alembic -c alembic.ini upgrade head
```

Run the due-availability assignment batch manually:

```powershell
docker-compose exec backend python -m app.commands.assign_due_availabilities --limit 100
```

Run one protected scheduler cycle:

```powershell
docker-compose exec -T -e ASSIGNMENT_SCHEDULER_ENABLED=true backend python -m app.commands.run_assignment_scheduler --once
```

Run the continuous scheduler service through the optional Compose profile:

```powershell
docker-compose --profile scheduler up -d assignment-scheduler
```

The API container keeps scheduler execution disabled by default. The optional `assignment-scheduler` service sets `ASSIGNMENT_SCHEDULER_ENABLED=true` because selecting the `scheduler` profile is the explicit enablement step. The scheduler uses a PostgreSQL advisory lock per cycle so overlapping scheduler instances skip work when another instance is already running. Production deployments should run the scheduler as a separate worker process, keep migrations ahead of worker startup, and alert on persistent cycle failures. Full scheduler configuration is documented in `resources/docs/assignment_scheduler.md`.

## Monitoring and Observability

Full monitoring guidance is in `resources/docs/monitoring_observability.md`.

Operational endpoints:

- `/health/live`: process liveness, no database check.
- `/health/ready`: readiness with a bounded PostgreSQL `SELECT 1` check.
- `/metrics`: Prometheus text-format metrics for internal scraping.

The local monitoring profile starts Prometheus and Grafana:

```powershell
docker-compose --profile monitoring up -d assignment-scheduler prometheus grafana
```

Local Prometheus and Grafana ports are bound to `127.0.0.1`. Production TLS proxy configuration blocks public `/metrics` and `/api/metrics`; scrape backend metrics from the internal network instead. If multiple backend worker processes are introduced, Prometheus Python multiprocess mode must be implemented before relying on application metrics.

## Environment Configuration

Required production decisions:

- `DATABASE_URL`: use the PostgreSQL `postgresql+psycopg://` URL for the deployment database.
- `DATABASE_PASSWORD_FILE` or `POSTGRES_PASSWORD_FILE`: preferred Docker-secret pattern when `DATABASE_URL` is not set and the URL is built from components.
- `JWT_SECRET_KEY`: replace the development value with a high-entropy secret from a secret manager.
- `JWT_SECRET_FILE`: preferred Docker-secret pattern for production Compose.
- `JWT_ALGORITHM`: defaults to `HS256`; coordinate any algorithm change with token consumers.
- `ACCESS_TOKEN_EXPIRE_MINUTES`: defaults to `30`.
- `CORS_ALLOWED_ORIGINS`: set an explicit JSON list of exact trusted frontend origins.
- `CORS_ALLOW_CREDENTIALS`: defaults to `false`; enable only when cookies, client certificates, or browser credential mode are required. Bearer `Authorization` headers do not require this flag.
- `ASSIGNMENT_SCHEDULER_*`: optional due-assignment scheduler controls. The scheduler is disabled by default and must be enabled explicitly for a dedicated worker/service.
- `METRICS_ENABLED`: enables `/metrics` and scheduler metrics server; defaults to `true`.
- `METRICS_PATH`: backend metrics path; defaults to `/metrics`.
- `SCHEDULER_METRICS_PORT`: internal scheduler metrics port; defaults to `9101`.
- `READINESS_DATABASE_TIMEOUT_SECONDS`: bounded PostgreSQL readiness timeout; defaults to `2`.
- `SEED_ADMIN_*`: optional local-only admin seed values. `SEED_ADMIN_ENABLED` must remain `false` outside explicit local smoke setup.
- `LOG_LEVEL`: defaults to `INFO`; accepted values are `DEBUG`, `INFO`, `WARNING`, `ERROR`, and `CRITICAL`.
- `LOG_JSON`: defaults to `true`; JSON logs are recommended for production ingestion.
- `VITE_API_BASE_URL`: browser-visible backend URL embedded into the frontend build.

Do not store production secrets in `.env.example`, source control, container images, or logs.

`DATABASE_URL` and a database password file are mutually exclusive. For production Compose, leave `DATABASE_URL` empty and provide component settings plus the password secret file so the backend builds a URL without exposing the password in committed configuration.

## Logging and Error Handling

The backend emits structured request completion and failure logs through standard Python logging. HTTP records contain the request ID, method, canonical route path, status code, and duration. Query strings, unmatched raw paths, request bodies, passwords, bearer tokens, authorization headers, user data, and exception messages are intentionally omitted. Unhandled error logs include the exception type and stack frames.

Clients may send a safe `X-Request-ID`; otherwise, the backend generates one. The response always returns `X-Request-ID`. Unhandled errors return:

```json
{
  "detail": "Internal server error",
  "request_id": "request-correlation-id",
  "error_code": "internal_server_error"
}
```

Unhandled exception stack traces are logged server-side and are never returned to clients. Existing HTTP and validation error bodies remain unchanged for API compatibility.

## API Security Baseline

- Passwords are stored using the existing Passlib bcrypt hashing helper. Plain passwords are never stored or returned.
- JWT access tokens are bearer credentials. Serve the backend only over HTTPS outside local development.
- The frontend currently stores bearer tokens in browser storage. Treat XSS prevention as critical. A future secure-cookie or backend-for-frontend session design would require CSRF protection and is not implemented in this MVP.
- CORS allows only configured exact HTTP(S) origins. Wildcards, URL paths, embedded credentials, and empty origin lists are rejected during settings validation.
- When `CORS_ALLOW_CREDENTIALS=true`, browsers require the response to name the exact requesting origin; wildcard origins are invalid and are not supported.
- `ENVIRONMENT=production` or `prod` rejects localhost and loopback CORS origins so deployment cannot silently retain local-development defaults.
- Allowed cross-origin methods are `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, and `OPTIONS`; allowed non-safelisted headers are `Authorization`, `Content-Type`, and `X-Request-ID`.
- Every backend response includes `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, and `Referrer-Policy: no-referrer`.
- Content Security Policy is not set by the API because the frontend is served separately. Configure CSP and other browser-facing headers on the frontend nginx or ingress layer.
- Role authorization remains enforced by backend dependencies; frontend route guards are not a security boundary.

The application does not currently implement SSO, refresh-token rotation, token revocation, rate limiting, CSRF tokens, audit-log export retention policy, or external secrets/logging systems.

## Future Company SSO/OIDC Integration

Actual SSO/OIDC integration is not implemented. The recommended future approach is OpenID Connect against the company identity provider, such as Microsoft Entra ID.

### Recommended Flow and Trust Boundary

- Use the OIDC authorization code flow with PKCE for the browser frontend.
- Register explicit HTTPS redirect URIs; do not use wildcard redirect URIs.
- Prefer a backend-for-frontend or secure server-managed session when practical. If the SPA sends provider access tokens directly, the backend must validate every token and the browser must avoid persistent insecure token storage.
- Validate token signature, issuer, intended audience, expiration, not-before time, and required claims on every protected request.
- Resolve signing keys from the trusted issuer discovery document and JWKS endpoint. Cache keys with bounded lifetime and refresh after an unknown key ID to support rotation.
- Never treat decoded-but-unverified claims as authenticated identity.

### Local Identity and Authorization Mapping

- Add an immutable external identity field based on provider issuer and subject/object identifier instead of matching only by mutable email.
- Map approved OIDC groups or application roles to the existing local `UserRole` values.
- Keep team membership as controlled local application data unless the organization defines an authoritative identity-provider group mapping.
- Deny access when required role/group claims are absent or ambiguous; never silently default an SSO user to admin.
- Audit identity linking and role/team mapping changes.

### Migration from Local Passwords

1. Add nullable external issuer/subject identity fields without removing current local authentication.
2. Link existing users through an authenticated, administratively reviewed process.
3. Run local and SSO authentication during a controlled transition while monitoring unmapped users.
4. Disable local password login for linked non-emergency accounts after adoption.
5. Retain password hashes only as long as the approved rollback policy requires, then remove them through a migration.

### Emergency Admin Fallback

- If a local emergency admin is retained, keep it disabled by default and outside normal daily use.
- Store its high-entropy credential in a protected secret manager with restricted and audited access.
- Require a documented break-glass process, short activation window, post-use review, and immediate credential rotation.
- Do not expose the fallback account through broad internet access.

### Session and Logout Considerations

- Use short-lived access/session tokens and validate expiration on every protected request.
- Store refresh tokens only in secure, HTTP-only, `Secure`, appropriately `SameSite` cookies or server-side encrypted storage; never persist them in browser local storage.
- Rotate refresh tokens when supported and detect reuse.
- Local logout can clear the application session but may not terminate the identity-provider session or already-issued tokens.
- Define a revocation strategy for disabled users, role changes, compromised sessions, and emergency-access removal. OIDC alone does not guarantee immediate revocation of previously issued self-contained tokens.

## PostgreSQL Backup and Restore

The Compose database uses the named `postgres_data` volume. Volume persistence is not a backup. Detailed backup and restore operations are documented in `resources/docs/postgres_backup_restore.md`.

Create a local custom-format backup with checksum metadata:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\backup_postgres.ps1
```

Verify a backup archive:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify_postgres_backup.ps1 -BackupFile .\backups\postgres\<backup>.pgdump
```

Restore into a fresh disposable database:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\restore_postgres.ps1 -BackupFile .\backups\postgres\<backup>.pgdump -TargetDatabase parking_app_restore_verify
```

The restore script refuses production-like restores unless `-AllowProductionRestore` is provided and refuses existing-database replacement unless `-ConfirmDestructive` is provided. Test backup and restore procedures against a staging database before relying on them. Production deployments should use encrypted scheduled backups, off-host storage, retention monitoring, and periodic restore drills.

## Production Checklist

- Replace all default database and JWT credentials through a secret manager or platform Docker/Kubernetes secrets.
- Confirm `ENVIRONMENT=production` fails closed when example secrets or local CORS origins are present.
- Confirm `SEED_ADMIN_ENABLED=false`; use the approved production identity-provisioning process instead.
- Terminate HTTPS at a trusted ingress or reverse proxy and redirect HTTP to HTTPS.
- Keep backend and database services off public host ports in production.
- Set explicit production CORS origins and browser-visible frontend API URL.
- Confirm `ENVIRONMENT=production` starts successfully with only approved non-local CORS origins.
- Apply Alembic migrations before serving traffic.
- Configure a scheduler for due-availability assignment with overlap prevention.
- Forward stdout/stderr logs to a protected log system and define retention.
- Configure database backups, retention, encryption, and restore tests.
- Configure Prometheus/Grafana or platform monitoring, readiness alerts, scheduler freshness alerts, and backup-job alerts.
- Restrict database network access and use least-privilege service credentials.
- Add platform health checks, restart policy, resource limits, and alerting.
- Review dependency vulnerabilities and access-control tests before release.
- Verify frontend CSP/security headers at the ingress or nginx layer.

## Known Deployment Limitations

- The normal `docker-compose.yml` definition is intended for local use. Production-oriented TLS and Docker secret groundwork is separate in `docker-compose.production.yml`, but it is still not a complete cloud deployment.
- Structured logs are written only to process stdout/stderr; no external aggregation, metrics, tracing, or alerting is configured.
- Request IDs correlate backend records only; they are not distributed tracing identifiers.
- Database backup and restore commands are examples and require environment-specific validation.
- The local admin seed command is intentionally unavailable outside local/development/test environments and does not solve production user provisioning.
