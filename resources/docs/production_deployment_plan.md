# Production Deployment Plan

## Purpose

This runbook describes a safe deployment of ParkingApp v1.0.0-mvp to a Linux VM or on-premises server. It covers the repository's current production Docker Compose baseline and the controls an operator must supply.

This plan does not deploy the application, publish images, provision infrastructure, or provide production secrets.

## Assumptions And Current Boundaries

- Target host: maintained 64-bit Linux.
- Docker Engine and Docker Compose v2 plugin are installed.
- Deployment uses the immutable v1.0.0-mvp release tag.
- The supported built-in database path is PostgreSQL 16 in the db container with the postgres_data named volume.
- An external PostgreSQL service is possible only through a reviewed Compose override. The current production file fixes DATABASE_HOST to db and depends on that service.
- HTTPS terminates at the provided nginx proxy or an equivalent external reverse proxy.
- Secrets and trusted TLS material arrive out-of-band and are never committed.
- GitHub Actions validates code but does not deploy.
- Images are built on the target from the tag; no image publication workflow exists.
- PowerShell 7 (pwsh) is required for the supplied backup, restore, verification, and local-certificate scripts on Linux.
- Prometheus/Grafana assets exist, but docker-compose.production.yml does not define those services. Production monitoring needs a reviewed override or external platform.
- Expected Alembic head: 0010.

## Target Architecture

    Internet or corporate clients
                |
           TCP 80 / 443
                |
    nginx proxy and Vue frontend
    - HTTP redirect and TLS
    - SPA history fallback
    - /api forwarded to backend
                |
       private Compose network
                |
         FastAPI backend
                |
      PostgreSQL 16 db container
       postgres_data volume

    optional scheduler profile:
      assignment-scheduler -> PostgreSQL

    optional monitoring:
      internal backend/scheduler metrics -> Prometheus/Grafana or external platform

    operator:
      backup/verify/restore -> encrypted off-host storage

Only the proxy should be client-accessible. Production Compose does not publish PostgreSQL or backend ports. Docker secrets are mounted read-only under /run/secrets. The proxy blocks public /metrics and /api/metrics.

## Server Prerequisites

### Host Software

- Current Ubuntu LTS, Debian stable, or maintained enterprise Linux.
- Docker Engine supporting Compose health dependencies and file-backed secrets.
- Docker Compose v2 plugin; verify with docker compose version.
- Git, curl, OpenSSL, and PowerShell 7.
- Accurate NTP time.
- Non-root deployment account with controlled Docker access.

Docker-group membership is root-equivalent. Restrict it, require key-based SSH and MFA where available, and audit access.

### Capacity

Initial MVP planning baseline, subject to measured load:

- 2 to 4 vCPU.
- 4 to 8 GB RAM.
- 20 GB for OS, images, and logs, plus monitored database and backup capacity.
- Durable SSD-backed PostgreSQL storage.
- Space for at least twice the active database size during restore drills.
- Headroom for image layers, JSON logs, metrics, and migration work.

### Network, DNS, And Firewall

- DNS A/AAAA record for the application hostname.
- Inbound 443 for users.
- Inbound 80 only for redirect or ACME requirements.
- SSH restricted to trusted administration networks.
- Never expose 5432, 8000, 9101, 9090, or 3000 publicly.
- Permit outbound source/image/package, certificate, backup, and monitoring destinations as required.
- Restrict an external database endpoint to approved application hosts and require database TLS.

Production defaults map HTTP to 8081 and HTTPS to 8443. Set HTTP_PORT=80 and HTTPS_PORT=443 for direct public serving, or retain defaults behind an external load balancer.

## Release Checkout

    git clone https://github.com/MilosevicNikola99/ParkingApp.git
    cd ParkingApp
    git fetch --tags --prune
    git checkout --detach v1.0.0-mvp
    git status --short
    git show --no-patch --decorate

Expected: detached release tag and clean status. Never deploy an uncommitted tree. Confirm the GitHub Release and required checks match the tag.

## Environment And Secrets

### Non-Secret Environment

Create deployment-only .env from .env.example and replace local values:

    POSTGRES_DB=parking_app
    POSTGRES_USER=parking_app_runtime
    HTTP_PORT=80
    HTTPS_PORT=443

    APP_NAME=Parking Management API
    DB_POOL_SIZE=10
    DB_MAX_OVERFLOW=10
    DB_POOL_TIMEOUT_SECONDS=30
    DB_POOL_RECYCLE_SECONDS=1800
    DB_POOL_PRE_PING=true

    JWT_ALGORITHM=HS256
    ACCESS_TOKEN_EXPIRE_MINUTES=30
    PRODUCTION_VITE_API_BASE_URL=/api
    PRODUCTION_CORS_ALLOWED_ORIGINS=["https://parking.example.com"]
    CORS_ALLOW_CREDENTIALS=false

    SAME_TEAM_PRIORITY_WINDOW_HOURS=2
    RECENT_WIN_FAIRNESS_WINDOW_DAYS=30
    RECENT_WIN_SOFT_LIMIT=2

    ASSIGNMENT_SCHEDULER_INTERVAL_SECONDS=60
    ASSIGNMENT_SCHEDULER_BATCH_LIMIT=100
    ASSIGNMENT_SCHEDULER_LOCK_KEY=740730001
    ASSIGNMENT_SCHEDULER_RUN_IMMEDIATELY=true

    METRICS_ENABLED=true
    METRICS_PATH=/metrics
    SCHEDULER_METRICS_PORT=9101
    READINESS_DATABASE_TIMEOUT_SECONDS=2
    LOG_LEVEL=INFO
    LOG_JSON=true

Production Compose forces ENVIRONMENT=production, disables seed admin, and disables scheduler work in the API process.

PRODUCTION_VITE_API_BASE_URL is public build-time configuration. Use /api with the supplied same-origin proxy. Do not use backend:8000 as a browser URL. CORS must contain exact HTTPS origins including scheme and any non-default port.

Remove local plaintext defaults such as POSTGRES_PASSWORD, DATABASE_PASSWORD, DATABASE_URL, JWT_SECRET_KEY, local CORS, seed values, and local Grafana credentials from production .env even though production Compose uses secret files.

### Required Secret Files

    install -d -m 700 secrets
    openssl rand -base64 48 > secrets/postgres_password.txt
    openssl rand -base64 64 > secrets/jwt_secret.txt
    install -m 600 /secure/inbox/fullchain.pem secrets/tls_certificate.pem
    install -m 600 /secure/inbox/privkey.pem secrets/tls_private_key.pem
    chmod 600 secrets/*.txt secrets/*.pem

Required files:

| File | Consumer | Requirement |
| --- | --- | --- |
| secrets/postgres_password.txt | db, backend, scheduler | unique database password |
| secrets/jwt_secret.txt | backend, scheduler | independent high-entropy JWT key |
| secrets/tls_certificate.pem | proxy | trusted certificate/full chain |
| secrets/tls_private_key.pem | proxy | matching restricted private key |

Use a secret manager, password manager, protected environment, or secure operator transfer. Never place values in Git, issue trackers, logs, backups, command arguments, or shell transcripts. Do not reuse secrets. JWT rotation invalidates active tokens; database rotation requires coordinated PostgreSQL and service changes.

## Database Plan

### Containerized PostgreSQL

The built-in production path runs postgres:16-alpine, does not publish 5432, checks health with pg_isready, and stores data in postgres_data.

- Put Docker data on durable monitored storage.
- Back up outside the volume and host.
- Monitor capacity, IOPS, connections, restart count, and backup time.
- Test major upgrades separately.
- Never remove postgres_data during normal stops or application rollback.

### External PostgreSQL

A managed/external service can provide HA, encryption, and backup operations, but requires a reviewed override that:

- removes or disables the db dependency;
- sets external host, port, and TLS connection settings;
- supplies credentials from the platform secret mechanism;
- configures backend and scheduler identically;
- removes local-volume lifecycle assumptions.

Changing only DATABASE_HOST is insufficient because production Compose sets it to db. Validate overrides in staging with docker compose config.

### Identity And Privilege

- Use a dedicated database and runtime role.
- Avoid superuser privileges for application traffic.
- Give the migration operator only required DDL rights.
- Restrict network access to backend, scheduler, migration, and backup processes.
- Require encryption in transit to external PostgreSQL.

### Migrations

Start db, wait for health, and migrate from the release image:

    docker compose --env-file .env -f docker-compose.production.yml up -d db
    docker compose --env-file .env -f docker-compose.production.yml ps
    docker compose --env-file .env -f docker-compose.production.yml run --rm backend alembic -c alembic.ini upgrade head
    docker compose --env-file .env -f docker-compose.production.yml run --rm backend alembic -c alembic.ini current
    docker compose --env-file .env -f docker-compose.production.yml run --rm backend alembic -c alembic.ini heads

Expected current/head: 0010.

Take and verify a backup before migration. Alembic downgrade does not guarantee safe data rollback. Prefer reviewed forward fixes. Restore only with incident approval and a tested backup.

## TLS And HTTPS

### Test Certificate

Self-signed certificates are only for test environments:

    pwsh -NoProfile -File ./scripts/generate_local_tls_certificate.ps1

Browsers will not trust them by default. Never use them publicly.

### Production Certificate

Use a trusted CA or organizational PKI. Verify certificate metadata and key match:

    openssl x509 -noout -subject -issuer -dates -in secrets/tls_certificate.pem
    openssl x509 -noout -modulus -in secrets/tls_certificate.pem | openssl sha256
    openssl rsa -noout -modulus -in secrets/tls_private_key.pem | openssl sha256

The nginx proxy redirects HTTP to HTTPS, supports TLS 1.2/1.3, serves Vue with history fallback, proxies /api, forwards request context, and blocks public metrics. HSTS is intentionally disabled until the real domain is proven. Automate and monitor renewal; replace files atomically and restart proxy.

An external proxy must preserve host, X-Forwarded-Proto, X-Forwarded-For, and X-Request-ID; provide SPA fallback; block direct backend and metrics access; and use the final HTTPS CORS origin.

## Deployment Procedure

### 1. Pre-Deployment Gate

- Approved change and maintenance window.
- Correct release tag and passing GitHub checks.
- Named deployment, database, rollback, and validation owners.
- Valid DNS and trusted certificate.
- Verified backup destination and restore plan.
- Current database revision and adequate disk space.
- No secrets in the checkout.

### 2. Prepare Configuration

    cp .env.example .env
    install -d -m 700 secrets
    # Edit only non-secret production values in .env.
    # Deliver required secret files securely.

### 3. Validate And Build

    docker compose --env-file .env -f docker-compose.production.yml config --quiet
    docker compose --env-file .env -f docker-compose.production.yml --profile scheduler config --quiet
    docker compose --env-file .env -f docker-compose.production.yml build backend proxy
    docker compose --env-file .env -f docker-compose.production.yml images

Current strategy builds locally from the tag. Record resulting image IDs.

### 4. Back Up Existing Database

For upgrades, create and verify an off-host pre-deployment backup before migration.

### 5. Start Database And Migrate

    docker compose --env-file .env -f docker-compose.production.yml up -d db
    docker compose --env-file .env -f docker-compose.production.yml ps
    docker compose --env-file .env -f docker-compose.production.yml run --rm backend alembic -c alembic.ini upgrade head
    docker compose --env-file .env -f docker-compose.production.yml run --rm backend alembic -c alembic.ini current

Stop if revision is not 0010.

### 6. Start Application

    docker compose --env-file .env -f docker-compose.production.yml up -d backend proxy

Optionally start one scheduler:

    docker compose --env-file .env -f docker-compose.production.yml --profile scheduler up -d assignment-scheduler

Do not claim production Prometheus/Grafana from this file; use a reviewed override or external monitoring.

### 7. Initial Validation

    docker compose --env-file .env -f docker-compose.production.yml ps
    docker compose --env-file .env -f docker-compose.production.yml logs --tail=200 backend proxy
    curl --fail --silent --show-error https://parking.example.com/api/health/live
    curl --fail --silent --show-error https://parking.example.com/api/health/ready
    curl --fail --silent --show-error --head https://parking.example.com/login

Then complete the post-deployment checklist.

## Common Compose Operations

Validate:

    docker compose --env-file .env -f docker-compose.production.yml config --quiet
    docker compose --env-file .env -f docker-compose.production.yml --profile scheduler config --quiet

Build:

    docker compose --env-file .env -f docker-compose.production.yml build backend proxy

Start or update:

    docker compose --env-file .env -f docker-compose.production.yml up -d db backend proxy
    docker compose --env-file .env -f docker-compose.production.yml --profile scheduler up -d assignment-scheduler

Status and logs:

    docker compose --env-file .env -f docker-compose.production.yml ps
    docker compose --env-file .env -f docker-compose.production.yml logs --tail=200 backend proxy db
    docker compose --env-file .env -f docker-compose.production.yml --profile scheduler logs --tail=200 assignment-scheduler
    docker compose --env-file .env -f docker-compose.production.yml logs -f backend

Restart one service:

    docker compose --env-file .env -f docker-compose.production.yml restart backend
    docker compose --env-file .env -f docker-compose.production.yml restart proxy

Restart does not rebuild. For changed image content:

    docker compose --env-file .env -f docker-compose.production.yml up -d --no-deps --build backend

Migration:

    docker compose --env-file .env -f docker-compose.production.yml run --rm backend alembic -c alembic.ini upgrade head
    docker compose --env-file .env -f docker-compose.production.yml run --rm backend alembic -c alembic.ini current

Safe stop preserving volume:

    docker compose --env-file .env -f docker-compose.production.yml --profile scheduler stop assignment-scheduler
    docker compose --env-file .env -f docker-compose.production.yml down

Never add -v during normal operations or rollback. Never run docker system prune --volumes without approved storage review.

## Backup And Restore

Repository scripts execute PostgreSQL tools in the Compose db service and accept -ComposeFiles.

Recommended policy:

- Daily or more frequent backups according to recovery point objective.
- Additional verified backup before migrations.
- Encrypted off-host immutable/versioned storage.
- Alert on backup, checksum, upload, age, and capacity failure.
- Start with 14-30 daily copies plus policy-driven weekly/monthly retention.
- Fresh-database restore drill at least quarterly and before major upgrades.
- Defined recovery point/time objectives and named owners.

Backups include PostgreSQL data and Alembic metadata. They exclude environment files, secrets, TLS keys, application images, Compose config, and monitoring data.

Use a location outside the repository:

    pwsh -NoProfile -File ./scripts/backup_postgres.ps1 -ComposeFiles docker-compose.production.yml -ProjectName parkingapp-prod -OutputDirectory /srv/parkingapp-backups/staging -RetentionDays 14

Verify:

    pwsh -NoProfile -File ./scripts/verify_postgres_backup.ps1 -ComposeFiles docker-compose.production.yml -ProjectName parkingapp-prod -BackupFile /srv/parkingapp-backups/staging/parking_app_TIMESTAMP.pgdump

Fresh restore drill:

    pwsh -NoProfile -File ./scripts/restore_postgres.ps1 -ComposeFiles docker-compose.production.yml -ProjectName parkingapp-prod -Environment production -AllowProductionRestore -BackupFile /secure/backup/parking_app_TIMESTAMP.pgdump -TargetDatabase parking_app_restore_verify

Production safety approval is required even for a fresh target. ExistingDatabase additionally requires -Mode ExistingDatabase and -ConfirmDestructive. Never use destructive restore without independently reviewing backup, target, maintenance window, and authority.

For external databases, use provider tooling or a reviewed adaptation; current scripts target Compose db.

## Monitoring, Logging, And Health

### Health

- GET /api/health/live: liveness through proxy.
- GET /api/health/ready: database-aware readiness.
- GET /api/health: compatibility liveness.
- Internal backend GET /metrics: Prometheus format, publicly blocked.

Readiness does not verify Alembic revision; check it separately.

### Monitoring

Assets include Prometheus scrape config, example alert rules, Grafana provisioning/dashboard, and backend/scheduler metrics. The local monitoring profile is not a production definition.

Use either a reviewed private Compose override or the organization's monitoring platform. Tune alerts before paging. Monitor:

- readiness, HTTP 5xx rate, and latency;
- scheduler errors, lock skips, and last success;
- PostgreSQL health, storage, connections, and latency;
- host disk, memory, CPU, and restarts;
- TLS expiry;
- backup age/failures;
- missing monitoring targets.

### Logging

Backend and scheduler emit JSON when LOG_JSON=true. Docker captures stdout/stderr. Configure bounded rotation or a log driver and forward to access-controlled storage.

    docker compose --env-file .env -f docker-compose.production.yml logs --since=30m --tail=500 backend proxy db

Use X-Request-ID for correlation. Never log authorization headers, JWTs, passwords, URLs containing credentials, secret contents, or credential request bodies.

## Scheduler Operation

The assignment-scheduler service is controlled by the scheduler profile. It runs the assignment command loop, processes bounded batches, uses a PostgreSQL advisory lock, emits internal metrics, and logs cycle outcomes.

Start:

    docker compose --env-file .env -f docker-compose.production.yml --profile scheduler up -d assignment-scheduler

Inspect:

    docker compose --env-file .env -f docker-compose.production.yml --profile scheduler ps assignment-scheduler
    docker compose --env-file .env -f docker-compose.production.yml --profile scheduler logs --since=30m assignment-scheduler

Temporarily disable:

    docker compose --env-file .env -f docker-compose.production.yml --profile scheduler stop assignment-scheduler

Run one MVP scheduler replica. Restart only after understanding database readiness, lock skips, and repeated failures.

## CI/CD Relationship

GitHub Actions validates backend tests/compile/Alembic/audit, PostgreSQL concurrency, frontend tests/build/audits, Compose/images, and Chromium MVP smoke. Required checks must pass before merge or tag.

CI does not publish images, connect to production, migrate production, or deploy. Release tags mark reviewed source baselines.

Future deployment automation should add immutable signed images, SBOM/provenance, protected environments, manual approval, pre-deployment backup and migration gates, health checks, and auditable rollback selection.

## Rollback Plan

1. Stop scheduler to prevent new assignment changes.
2. Record image IDs, logs, migration revision, and incident timeline.
3. Determine whether database schema/data changed.
4. Check out the previous approved tag in a separate clean directory, or use immutable previous images when available.
5. Restore reviewed configuration references.
6. Build/start previous backend and proxy.
7. Verify health, login, and critical workflows.
8. Restart scheduler only after data compatibility is confirmed.

Do not use git reset --hard as a deployment mechanism and never move release tags.

Application rollback is safe only when old code supports the current schema/data. Alembic downgrade can be destructive. Inspect migrations, irreversible transformations, and compatibility before any downgrade.

Restore a backup only when the accepted recovery point permits loss of later writes. If post-migration writes occurred, a forward repair or manual data repair can be safer. Escalate rather than guessing.

## Post-Deployment Validation Checklist

- [ ] Correct tag and commit deployed.
- [ ] Expected containers running without restart loops.
- [ ] PostgreSQL healthy and persistent storage mounted.
- [ ] Alembic current and heads report 0010.
- [ ] Certificate hostname, chain, and expiry valid.
- [ ] HTTP redirects to HTTPS.
- [ ] /api/health/live returns 200.
- [ ] /api/health/ready returns 200.
- [ ] /login is reachable over HTTPS and route refresh works.
- [ ] Approved validation login works.
- [ ] Admin dashboard and operational pages load.
- [ ] Owner publishes availability from owned spot without manual spot ID.
- [ ] Employee sees availability and applies.
- [ ] Assignment smoke creates expected reservation and audit.
- [ ] Reports and one CSV export work.
- [ ] Public metrics routes are blocked.
- [ ] Internal backend/scheduler metrics scrape.
- [ ] Request IDs correlate responses and logs.
- [ ] Backup is created and verified.
- [ ] No critical errors, restarts, auth leaks, or secret values in logs.
- [ ] Scheduler has recent success or is deliberately disabled.
- [ ] Monitoring and alerts receive current data.
- [ ] Resource and certificate thresholds are healthy.

Use disposable records and remove them according to policy. Do not run destructive tests in production.

## Operational Runbook

### Backend Unhealthy

Check service state, backend logs, restart count, memory/disk, and liveness. If live but not ready, inspect database and migration revision. Confirm secret files exist without printing them. Stop traffic or roll back if unresolved.

### Frontend Cannot Reach API

Check browser errors and /api/health/live. Confirm proxy build used /api, inspect proxy logs/routing, and verify HTTPS origin, CORS, and forwarded headers.

### Database Connection Failure

Check db health/logs, volume, database identity, password-file mount, disk, connections, and network/TLS for external database. Never expose 5432 as a quick fix.

### Migration Failure

Stop rollout and scheduler. Capture Alembic output/current/head, confirm image and backup, and inspect partial application. Do not rerun blindly. Choose reviewed forward fix, compatible rollback, or restore.

### TLS Issue

Inspect dates, chain, hostname, key match, paths, and permissions. Replace atomically and restart proxy. Never disable validation for production users.

### CORS Issue

Compare browser Origin exactly with PRODUCTION_CORS_ALLOWED_ORIGINS. Include scheme and port. Recreate backend after changes. Never use a broad wildcard.

### Scheduler Not Assigning

Check state, logs, readiness, advisory-lock skips, last-success metrics, interval, batch limit, and due records. Stop it if cycles repeatedly fail.

### Backup Failure

Check db health, pwsh, output permissions, disk, and destination. Preserve safe logs and the last good backup. Escalate when recovery objectives are threatened.

### Disk Full

Stop scheduler and nonessential writes if integrity is threatened. Identify database, images, logs, metrics, or backup staging usage. Remove only reviewed disposable artifacts; never prune volumes blindly.

### Monitoring Unavailable

Verify application health independently. Check scrape reachability, storage, and credentials. Establish temporary manual checks. Never expose metrics publicly as a workaround.

## Security Checklist

- [ ] Unique high-entropy JWT secret.
- [ ] Unique non-default database password.
- [ ] No committed .env, secrets, keys, certificates, backups, or artifacts.
- [ ] Trusted HTTPS and modern TLS.
- [ ] Exact production CORS origins.
- [ ] Database, backend, metrics, Prometheus, and Grafana are private.
- [ ] Least-privilege audited server access.
- [ ] Seed admin disabled.
- [ ] Regular dependency and base-image review.
- [ ] Encrypted, access-controlled, verified backups and restore drills.
- [ ] Protected logs reviewed for sensitive data.
- [ ] Patch, certificate, firewall, and backup owners/schedules defined.

## Optional Future Automation

- Private registry with signed immutable images.
- SBOM and provenance.
- GitHub deployment workflow with protected environment/manual approval.
- Secret manager integration.
- Blue/green or rolling rollout where schema compatibility permits.
- Migration approval and compatibility gates.
- Scheduled encrypted off-host backups.
- Uptime, certificate, login, and assignment synthetic monitoring.
- Production monitoring definition with private access and persistent storage.

## Final Operational Gate

Approve deployment only when release provenance and CI checks are confirmed, secrets/config are reviewed, backup is verified, migration/rollback owners are present, monitoring/communications are active, validation is assigned, and no critical defect remains.

Related documents:

- resources/docs/production_secrets_tls.md
- resources/docs/postgres_backup_restore.md
- resources/docs/monitoring_observability.md
- resources/docs/ci_pipeline.md
- resources/docs/developer_handoff.md
- resources/docs/release_notes_v1.0.0-mvp.md
