# Staging Deployment Rehearsal

## Rehearsal Goal

Use this checklist to prove that the ParkingApp v1.0.0-mvp production deployment path can be operated safely before any production rollout.

The rehearsal must:

- start from a clean staging host and immutable release tag;
- use synthetic users, data, database credentials, and JWT secret;
- validate production Docker Compose, TLS, migrations, health, role workflows, scheduler behavior, logs, backup/verification, disposable restore, and rollback steps;
- record every failure and retest;
- leave no production credentials, production data, published images, or unreviewed infrastructure behind.

This is an operator rehearsal, not a production deployment.

## Current Boundaries

- The supported rehearsal path uses docker-compose.production.yml with its containerized PostgreSQL db service.
- External PostgreSQL requires a reviewed override and is outside this baseline rehearsal.
- The production Compose file includes db, backend, proxy, and the optional assignment-scheduler service under the scheduler profile.
- Prometheus/Grafana are not declared in docker-compose.production.yml. Monitoring can use an approved external platform or a separately reviewed staging override.
- Production Compose forces long-running services to ENVIRONMENT=production and disables admin seeding.
- The seed command permits only local, development, or test environments. The bootstrap step therefore overrides ENVIRONMENT=test only in a one-off container; the running staging backend remains production mode.
- The repository TLS helper creates a localhost certificate. Use it only when testing through localhost. A staging hostname needs a matching temporary/trusted certificate supplied by the operator.
- Expected Alembic head is 0010.

## Roles And Evidence

Assign before starting:

| Role | Responsibility |
| --- | --- |
| Rehearsal lead | approves steps, owns stop/go decisions |
| Application operator | executes Compose, migration, scheduler, and smoke steps |
| Database operator | backup, restore, revision, and data-safety checks |
| Security/network operator | secrets, DNS, TLS, firewall, and log review |
| Observer/recorder | timestamps evidence, failures, fixes, and acceptance |
| Rollback owner | decides and executes rollback simulation |

Store screenshots, command output, timestamps, image IDs, revision output, and failure records in an approved evidence location. Redact secrets, tokens, cookies, personal data, and private keys.

## Preconditions

- [ ] Annotated tag v1.0.0-mvp exists remotely and matches the GitHub Release.
- [ ] Hosted backend, PostgreSQL concurrency, frontend, Compose/image, audit, and E2E checks are green.
- [ ] Staging server and maintenance window are approved.
- [ ] Docker Engine and Docker Compose v2 are available.
- [ ] Git, curl, OpenSSL, and PowerShell 7 are installed.
- [ ] Staging DNS or an approved temporary hostname is available.
- [ ] TLS strategy is selected: trusted staging certificate, approved internal CA, or documented self-signed localhost-only test.
- [ ] Inbound firewall exposes only approved SSH, HTTP redirect, and HTTPS ports.
- [ ] No production database, account, credential, certificate key, backup, or user data will be used.
- [ ] Backup staging directory and off-host evidence location are approved.
- [ ] Monitoring decision is recorded: external monitoring, reviewed override, or manual checks for the rehearsal.
- [ ] Rollback owner and stop conditions are agreed.
- [ ] Current repository working tree on the operator workstation is not used as the deployment source.

## Required Inputs

Record references, not secret values:

| Input | Rehearsal value/reference |
| --- | --- |
| Staging domain | |
| Server hostname/IP | |
| Release tag and commit | v1.0.0-mvp / |
| HTTPS port | |
| Synthetic PostgreSQL database name | parking_app_staging |
| Synthetic PostgreSQL user | parking_app_staging |
| PostgreSQL password secret location | |
| JWT secret location | |
| Exact HTTPS CORS origin | |
| TLS certificate path | |
| TLS private key path | |
| Backup staging directory | |
| Off-host backup/evidence destination | |
| Synthetic admin email/username reference | |
| Synthetic admin password reference | |
| Monitoring decision | |
| Rehearsal lead / rollback owner | |

Do not paste secret values into this document, tickets, chat, screenshots, shell history, or logs.

## Staging Directory Layout

Recommended host paths:

    /srv/parkingapp-staging/source
    /srv/parkingapp-staging/secrets
    /srv/parkingapp-staging/backups
    /srv/parkingapp-staging/evidence
    /secure/parkingapp/staging-seed.env

The source checkout contains no secrets. Secret and backup directories must be outside Git control and restricted to approved operators.

## Step-By-Step Rehearsal

### 1. Record Host Baseline

    date --utc
    uname -a
    docker version
    docker compose version
    git --version
    pwsh --version
    openssl version
    df -h
    free -h

Acceptance:

- Supported tools execute.
- Time is synchronized.
- Disk and memory have agreed headroom.
- No existing ParkingApp staging containers, network, or volume conflict with the selected project name.

Inspect without deleting:

    docker ps -a
    docker volume ls
    docker network ls

Use a dedicated project name in every Compose command:

    export COMPOSE_PROJECT_NAME=parkingapp-staging

### 2. Clone And Verify Release

    install -d -m 750 /srv/parkingapp-staging
    cd /srv/parkingapp-staging
    git clone https://github.com/MilosevicNikola99/ParkingApp.git source
    cd source
    git fetch --tags --prune
    git checkout --detach v1.0.0-mvp
    git status --short
    git show --no-patch --decorate --format=fuller

Acceptance:

- HEAD is the released tag.
- Working tree is clean.
- Commit matches the GitHub Release.
- No operator modifications are present.

### 3. Prepare Synthetic Non-Secret Environment

    cp .env.example .env
    chmod 600 .env

Edit .env with staging-only values:

    POSTGRES_DB=parking_app_staging
    POSTGRES_USER=parking_app_staging
    HTTP_PORT=8081
    HTTPS_PORT=8443

    APP_NAME=Parking Management API - Staging
    PRODUCTION_VITE_API_BASE_URL=/api
    PRODUCTION_CORS_ALLOWED_ORIGINS=["https://staging-parking.example.test:8443"]
    CORS_ALLOW_CREDENTIALS=false

    DB_POOL_SIZE=5
    DB_MAX_OVERFLOW=5
    DB_POOL_TIMEOUT_SECONDS=30
    DB_POOL_RECYCLE_SECONDS=1800
    DB_POOL_PRE_PING=true

    JWT_ALGORITHM=HS256
    ACCESS_TOKEN_EXPIRE_MINUTES=30
    SAME_TEAM_PRIORITY_WINDOW_HOURS=0
    RECENT_WIN_FAIRNESS_WINDOW_DAYS=30
    RECENT_WIN_SOFT_LIMIT=2

    ASSIGNMENT_SCHEDULER_INTERVAL_SECONDS=30
    ASSIGNMENT_SCHEDULER_BATCH_LIMIT=100
    ASSIGNMENT_SCHEDULER_LOCK_KEY=740730101
    ASSIGNMENT_SCHEDULER_RUN_IMMEDIATELY=true

    METRICS_ENABLED=true
    METRICS_PATH=/metrics
    SCHEDULER_METRICS_PORT=9101
    READINESS_DATABASE_TIMEOUT_SECONDS=2
    LOG_LEVEL=INFO
    LOG_JSON=true

Remove local plaintext values from the staging file:

- POSTGRES_PASSWORD
- DATABASE_PASSWORD
- DATABASE_URL
- JWT_SECRET_KEY
- local CORS origins
- seed-admin values
- local Grafana defaults

The priority window is set to zero only to make the rehearsal assignment deterministic and immediate. Record this staging difference.

### 4. Create Synthetic Secret Files

    install -d -m 700 secrets
    openssl rand -base64 48 > secrets/postgres_password.txt
    openssl rand -base64 64 > secrets/jwt_secret.txt
    chmod 600 secrets/postgres_password.txt secrets/jwt_secret.txt

Install a certificate matching the rehearsal hostname:

    install -m 600 /secure/inbox/staging-fullchain.pem secrets/tls_certificate.pem
    install -m 600 /secure/inbox/staging-privkey.pem secrets/tls_private_key.pem

For localhost-only testing, the existing helper may be used:

    pwsh -NoProfile -File ./scripts/generate_local_tls_certificate.ps1

Do not use the localhost helper for a non-local staging hostname.

Verify certificate metadata without printing private material:

    openssl x509 -noout -subject -issuer -dates -in secrets/tls_certificate.pem
    openssl x509 -noout -modulus -in secrets/tls_certificate.pem | openssl sha256
    openssl rsa -noout -modulus -in secrets/tls_private_key.pem | openssl sha256

Acceptance:

- Secrets are synthetic and unique.
- File permissions are restricted.
- Certificate hostname and key match.
- secrets is ignored by Git.
- No value appears in evidence output.

### 5. Validate Compose Configuration

    docker compose --env-file .env -f docker-compose.production.yml config --quiet
    docker compose --env-file .env -f docker-compose.production.yml --profile scheduler config --quiet
    docker compose --env-file .env -f docker-compose.production.yml config --services
    docker compose --env-file .env -f docker-compose.production.yml --profile scheduler config --services

Expected default services:

- db
- backend
- proxy

Expected scheduler profile adds:

- assignment-scheduler

Review rendered configuration without exporting it to public evidence. Confirm:

- no host mapping for PostgreSQL or backend;
- proxy uses staging HTTP/HTTPS ports;
- secret files map to /run/secrets;
- backend and scheduler target db;
- seed admin is false for long-running services;
- CORS origin is the exact staging HTTPS origin.

### 6. Build Images

    docker compose --env-file .env -f docker-compose.production.yml build backend proxy
    docker compose --env-file .env -f docker-compose.production.yml images

Record image IDs and build duration. Do not push images.

Acceptance:

- Builds use the checked-out release.
- No dependency or frontend build failure.
- No secret value is copied into image layers or build output.
- Proxy frontend build uses /api.

### 7. Start PostgreSQL

    docker compose --env-file .env -f docker-compose.production.yml up -d db
    docker compose --env-file .env -f docker-compose.production.yml ps db
    docker compose --env-file .env -f docker-compose.production.yml logs --tail=100 db

Wait until db is healthy. Confirm the staging volume:

    docker volume ls --filter name=parkingapp-staging

Do not continue if the database restarts, reports corruption, or uses an unexpected volume.

### 8. Apply And Verify Migrations

    docker compose --env-file .env -f docker-compose.production.yml run --rm backend alembic -c alembic.ini upgrade head
    docker compose --env-file .env -f docker-compose.production.yml run --rm backend alembic -c alembic.ini current
    docker compose --env-file .env -f docker-compose.production.yml run --rm backend alembic -c alembic.ini heads
    docker compose --env-file .env -f docker-compose.production.yml run --rm backend alembic -c alembic.ini history

Acceptance:

- Upgrade exits successfully.
- Current and heads report 0010.
- One linear head exists.
- No secret or connection URL is printed.

### 9. Start Backend And Proxy

    docker compose --env-file .env -f docker-compose.production.yml up -d backend proxy
    docker compose --env-file .env -f docker-compose.production.yml ps
    docker compose --env-file .env -f docker-compose.production.yml logs --tail=150 backend proxy

Set the public rehearsal URL:

    export STAGING_URL=https://staging-parking.example.test:8443

For a trusted certificate:

    curl --fail --silent --show-error $STAGING_URL/api/health/live
    curl --fail --silent --show-error $STAGING_URL/api/health/ready
    curl --fail --silent --show-error --head $STAGING_URL/login

Use curl -k only for an explicitly approved self-signed rehearsal, record that exception, and never carry it into production instructions.

Verify HTTP redirect:

    curl --head http://staging-parking.example.test:8081/login

Acceptance:

- HTTP redirects to HTTPS.
- Live and ready return 200.
- Login route returns 200 through SPA fallback.
- Security and X-Request-ID headers are present.
- Public metrics paths return 404.

    curl --include $STAGING_URL/api/health/live
    curl --fail --silent --show-error --output /dev/null --write-out "%{http_code}
" $STAGING_URL/metrics
    curl --fail --silent --show-error --output /dev/null --write-out "%{http_code}
" $STAGING_URL/api/metrics

The last two commands intentionally return 404; do not use curl --fail for those checks.

### 10. Bootstrap Synthetic Admin Safely

Create an operator-only file outside the repository:

    install -d -m 700 /secure/parkingapp
    install -m 600 /dev/null /secure/parkingapp/staging-seed.env

Populate it securely with synthetic values:

    SEED_ADMIN_EMAIL=staging.admin@example.test
    SEED_ADMIN_USERNAME=staging_admin
    SEED_ADMIN_PASSWORD=<synthetic-high-entropy-value>
    SEED_ADMIN_FIRST_NAME=Staging
    SEED_ADMIN_LAST_NAME=Admin
    SEED_ADMIN_UPDATE_PASSWORD=true

Load values into the current shell without echoing them:

    set -a
    . /secure/parkingapp/staging-seed.env
    set +a

Run the existing seed command in a one-off container. ENVIRONMENT=test is limited to this command because the seed safety guard rejects staging and production. Long-running services remain production mode.

    docker compose --env-file .env -f docker-compose.production.yml run --rm       -e ENVIRONMENT=test       -e SEED_ADMIN_ENABLED=true       -e SEED_ADMIN_EMAIL       -e SEED_ADMIN_USERNAME       -e SEED_ADMIN_PASSWORD       -e SEED_ADMIN_FIRST_NAME       -e SEED_ADMIN_LAST_NAME       -e SEED_ADMIN_UPDATE_PASSWORD       backend python -m app.commands.seed_admin

Immediately clear shell values:

    unset SEED_ADMIN_EMAIL SEED_ADMIN_USERNAME SEED_ADMIN_PASSWORD
    unset SEED_ADMIN_FIRST_NAME SEED_ADMIN_LAST_NAME SEED_ADMIN_UPDATE_PASSWORD

Acceptance:

- Command reports created or updated.
- Password is never printed.
- No seed settings are added to .env.
- Running backend still reports production environment.
- Operator seed file remains outside the repository and is removed after the rehearsal according to policy.

### 11. Manual Role Smoke Workflow

Record IDs and timestamps using synthetic names.

Admin:

- [ ] Open the staging HTTPS URL and log in as synthetic admin.
- [ ] Confirm dashboard and Help load.
- [ ] Create one synthetic team.
- [ ] Create one employee assigned to that team.
- [ ] Create one parking owner.
- [ ] Create one active parking spot owned by that parking owner.
- [ ] Confirm applications, reservations, audit logs, overrides, and reports pages load.

Parking owner:

- [ ] Log out and log in as parking owner.
- [ ] Confirm only owned active spots are available.
- [ ] Publish a near-term availability.
- [ ] Confirm no manual Parking spot ID field appears.
- [ ] Confirm availability appears in My availabilities and available spots.

Employee:

- [ ] Log out and log in as employee.
- [ ] Confirm role navigation does not expose admin/owner actions.
- [ ] View the available spot.
- [ ] Apply once.
- [ ] Confirm the application appears in My applications.

Assignment:

Choose one method and record it.

One-shot command before scheduler is enabled:

    docker compose --env-file .env -f docker-compose.production.yml run --rm backend       python -m app.commands.assign_due_availabilities --limit 100

Or enable scheduler in the next step and wait for a cycle.

Verify:

- [ ] Employee sees the reservation.
- [ ] Availability status changed correctly.
- [ ] Application status changed correctly.
- [ ] Admin sees reservation/history and assignment audit.
- [ ] Reports load and one CSV export succeeds.
- [ ] Logout/login preserves correct role navigation and denies unauthorized routes.

### 12. Scheduler Rehearsal

Start one scheduler:

    docker compose --env-file .env -f docker-compose.production.yml --profile scheduler up -d assignment-scheduler
    docker compose --env-file .env -f docker-compose.production.yml --profile scheduler ps assignment-scheduler
    docker compose --env-file .env -f docker-compose.production.yml --profile scheduler logs --since=10m assignment-scheduler

Create a second synthetic availability/application cycle and wait at least two configured intervals.

Acceptance:

- Scheduler remains running.
- A successful cycle is logged.
- Due work is assigned once.
- Repeated cycles do not duplicate active reservations.
- Advisory-lock or error behavior is visible without secret values.
- Temporarily stopping scheduler does not stop backend:

    docker compose --env-file .env -f docker-compose.production.yml --profile scheduler stop assignment-scheduler
    curl --fail --silent --show-error $STAGING_URL/api/health/ready

Restart after verification if required.

### 13. Monitoring And Logging Rehearsal

Direct backend metrics are private in production Compose. Inspect inside the Compose network with a temporary curl container:

    docker run --rm --network parkingapp-staging_default curlimages/curl:8.12.1       --fail --silent http://backend:8000/metrics > /tmp/parkingapp-staging-metrics.txt

Review metric names without publishing values:

    grep -E "parking_(http|readiness|assignment)" /tmp/parkingapp-staging-metrics.txt | head

Remove temporary evidence after recording approved excerpts:

    rm -f /tmp/parkingapp-staging-metrics.txt

If an approved monitoring override or external platform is enabled:

- [ ] Prometheus target for backend is up.
- [ ] Scheduler target is up when scheduler runs.
- [ ] Example rules load without errors.
- [ ] Grafana datasource and ParkingApp dashboard load.
- [ ] Monitoring ports remain private.
- [ ] A controlled scheduler stop or readiness test produces expected non-paging staging evidence.

Structured logs:

    docker compose --env-file .env -f docker-compose.production.yml logs --since=30m backend proxy db
    docker compose --env-file .env -f docker-compose.production.yml --profile scheduler logs --since=30m assignment-scheduler

Acceptance:

- JSON backend/scheduler logs are readable.
- X-Request-ID response values can be correlated.
- No password, JWT, Authorization header, secret content, or connection URL appears.
- No unexpected restart loop or critical exception exists.

### 14. Create And Verify Backup

Create a backup outside the repository:

    install -d -m 700 /srv/parkingapp-staging/backups
    pwsh -NoProfile -File ./scripts/backup_postgres.ps1       -ComposeFiles docker-compose.production.yml       -ProjectName parkingapp-staging       -DatabaseName parking_app_staging       -DatabaseUser parking_app_staging       -OutputDirectory /srv/parkingapp-staging/backups       -RetentionDays 7

List file names and permissions, not secret content:

    find /srv/parkingapp-staging/backups -maxdepth 1 -type f -printf "%f %s bytes
"

Verify the generated archive:

    pwsh -NoProfile -File ./scripts/verify_postgres_backup.ps1       -ComposeFiles docker-compose.production.yml       -ProjectName parkingapp-staging       -BackupFile /srv/parkingapp-staging/backups/parking_app_staging_TIMESTAMP.pgdump

Acceptance:

- Archive and metadata sidecar exist.
- Checksum and pg_restore archive validation pass.
- Metadata reports Alembic 0010.
- Backup is not inside the repository.
- An approved encrypted off-host copy can be made.

### 15. Disposable Restore Drill

Keep the live staging database intact. Restore into a new synthetic database:

    pwsh -NoProfile -File ./scripts/restore_postgres.ps1       -ComposeFiles docker-compose.production.yml       -ProjectName parkingapp-staging       -DatabaseUser parking_app_staging       -SourceDatabaseName parking_app_staging       -Environment production       -AllowProductionRestore       -BackupFile /srv/parkingapp-staging/backups/parking_app_staging_TIMESTAMP.pgdump       -TargetDatabase parking_app_staging_restore_verify

Verify revision and representative counts:

    docker compose --env-file .env -f docker-compose.production.yml exec -T db       psql -U parking_app_staging -d parking_app_staging_restore_verify -At       -c "SELECT version_num FROM alembic_version LIMIT 1;"

    docker compose --env-file .env -f docker-compose.production.yml exec -T db       psql -U parking_app_staging -d parking_app_staging_restore_verify -At       -c "SELECT count(*) FROM users; SELECT count(*) FROM teams; SELECT count(*) FROM parking_reservations;"

Acceptance:

- Restored revision is 0010.
- Representative synthetic data exists.
- Original staging database remains healthy.

Drop only the disposable restore database after evidence review:

    docker compose --env-file .env -f docker-compose.production.yml exec -T db       dropdb -U parking_app_staging parking_app_staging_restore_verify

### 16. Rollback Rehearsal

Because v1.0.0-mvp is the first release, a previous production tag may not exist. Choose and record one safe simulation:

A. Application/configuration rollback simulation using the same tag:

1. Record current image IDs, revision, config checksum reference, and health.
2. Stop scheduler.
3. Stop backend and proxy while preserving db/volume.
4. Rebuild the same immutable tag in a clean checkout.
5. Restore the previously approved staging configuration references.
6. Start backend/proxy.
7. Verify health and login.
8. Restart scheduler only after compatibility is confirmed.

Commands:

    docker compose --env-file .env -f docker-compose.production.yml --profile scheduler stop assignment-scheduler
    docker compose --env-file .env -f docker-compose.production.yml stop proxy backend
    git status --short
    git describe --tags --exact-match
    docker compose --env-file .env -f docker-compose.production.yml build backend proxy
    docker compose --env-file .env -f docker-compose.production.yml up -d backend proxy

B. Previous-tag rollback, only when an approved previous tag exists:

- Check out that tag in a separate clean directory.
- Confirm it supports the current database schema.
- Use immutable previous images if registry publication is introduced.
- Never move or recreate tags.

Database rollback rehearsal:

- Use the disposable restore drill as proof of backup recoverability.
- Do not replace the live staging database unless a separately approved destructive exercise exists.
- Alembic downgrade is not automatically safe.
- If post-migration writes exist, restoring an older backup loses them.
- Decide among compatible app rollback, reviewed downgrade, forward repair, manual data repair, or restore based on schema/data analysis.

Rollback acceptance:

- Services restart from a known source/config baseline.
- Health and synthetic admin login recover.
- Database compatibility decision and authority are documented.
- No volume is deleted and no unapproved destructive restore occurs.

### 17. Clean Stop

Capture final status/log evidence, then stop while preserving the database volume:

    docker compose --env-file .env -f docker-compose.production.yml --profile scheduler stop assignment-scheduler
    docker compose --env-file .env -f docker-compose.production.yml down
    docker compose --env-file .env -f docker-compose.production.yml ps
    docker volume ls --filter name=parkingapp-staging

Do not add -v until evidence, backup, and teardown approval are complete.

If full teardown is explicitly approved after a verified backup:

    docker compose --env-file .env -f docker-compose.production.yml down -v

Before that destructive command, independently confirm COMPOSE_PROJECT_NAME=parkingapp-staging and the exact volume name. Never prune unrelated volumes.

Remove or rotate synthetic seed credentials and staging certificates according to policy. Preserve only approved redacted evidence and encrypted backups.

## Acceptance Criteria

The rehearsal is READY only when all are true:

- [ ] Stack starts from a documented clean staging server state.
- [ ] Release source is exactly v1.0.0-mvp.
- [ ] Default and scheduler Compose configurations validate.
- [ ] Database reaches Alembic head 0010.
- [ ] Frontend is reachable over trusted HTTPS, or the staging TLS exception is documented.
- [ ] Liveness and readiness pass.
- [ ] Admin, owner, and employee smoke workflow passes.
- [ ] Owner publishes without manual parking spot ID.
- [ ] One-shot assignment or scheduler creates one correct reservation and audit.
- [ ] Role navigation and authorization behave correctly.
- [ ] Structured logs and request IDs are usable and contain no secrets.
- [ ] Internal metrics are accessible and public metrics are blocked.
- [ ] Backup is created and verified.
- [ ] Backup restores into a disposable database with revision 0010.
- [ ] Rollback procedure is executed or safely simulated and understood.
- [ ] No production credential, production data, or real employee identity is used.
- [ ] Failures are resolved/retested or explicitly block acceptance.
- [ ] Evidence and cleanup are complete.

Final result:

| Field | Value |
| --- | --- |
| Rehearsal date/time | |
| Release tag/commit | |
| Server/environment | |
| Lead | |
| Result: READY / FAILED / BLOCKED | |
| Open defects | |
| Production recommendation | |
| Evidence location | |

A failed acceptance item becomes the next deployment defect. Do not proceed to production with unresolved critical or high-risk findings.

## Failure Log

| Timestamp UTC | Step | Observed failure | Root cause | Fix | Retest result | Owner |
| --- | --- | --- | --- | --- | --- | --- |
| | | | | | | |
| | | | | | | |
| | | | | | | |

For each defect also record expected behavior, actual behavior, exact command/page, affected role/service, sanitized logs, severity, and production impact.

## Operator Sign-Off

- [ ] Rehearsal lead approves evidence.
- [ ] Application operator approves deployment commands.
- [ ] Database operator approves backup/restore and rollback conclusions.
- [ ] Security/network operator approves secrets, TLS, CORS, ports, and logs.
- [ ] Monitoring owner approves visibility or records the temporary limitation.
- [ ] All synthetic credentials are rotated/removed.
- [ ] Production go/no-go recommendation is recorded.

## Related Documentation

- resources/docs/production_deployment_plan.md
- resources/docs/production_secrets_tls.md
- resources/docs/postgres_backup_restore.md
- resources/docs/monitoring_observability.md
- resources/docs/ci_pipeline.md
- resources/docs/manual_qa_checklist.md
- resources/docs/release_notes_v1.0.0-mvp.md
