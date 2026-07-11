# PostgreSQL Concurrency and Load Validation

## Phase 1 - Assignment and Application Creation

Status: READY

QA date: 2026-06-21

Environment:

- Local Windows development machine with Docker Desktop.
- Disposable Compose project: `parkingappconcurrencyphase1`.
- Disposable PostgreSQL database: `parking_app_concurrency`.
- Disposable PostgreSQL volume: `parkingappconcurrencyphase1_postgres_data`, removed after verification.
- Normal development PostgreSQL volume was not used.

## Scope

Phase 1 covered deterministic PostgreSQL concurrency tests for:

- Two concurrent scheduler assignment attempts for the same due availability.
- One advisory-lock-protected scheduler cycle overlapping with one direct assignment call.
- Two direct assignment calls for the same availability.
- Two direct assignment calls for different availabilities.
- Concurrent duplicate application creation by the same employee.
- Concurrent application creation by different employees.
- Application submission overlapping with assignment start.

Out of scope for this phase:

- Cancellation concurrency.
- Reassignment concurrency.
- Admin manual override and replacement override concurrency.
- General load-test harness.
- Moderate or stress load profiles.
- Connection-pool tuning.
- Broad performance benchmarking.

## Current Lock Order

Scheduled assignment runner:

1. Acquires the PostgreSQL session-level advisory lock with `pg_try_advisory_lock`.
2. Lists due assignable availabilities without row locks.
3. For each due availability, delegates to the assignment service.
4. Commits or rolls back each availability assignment independently.
5. Releases the advisory lock when the cycle exits.

Direct assignment and scheduler assignment service:

1. Locks the target `parking_availabilities` row with `SELECT ... FOR UPDATE`.
2. Verifies the availability is still open.
3. Checks for an existing reservation.
4. Locks pending `parking_applications` rows for that availability with `SELECT ... FOR UPDATE`.
5. Ranks candidates with the existing ranking policy.
6. Inserts the reservation.
7. Updates the selected application to `selected`.
8. Updates losing pending applications to `rejected`.
9. Updates the availability to `assigned`.
10. Inserts the assignment audit log in the same transaction.
11. Caller commits or rolls back the transaction.

Application creation:

1. Locks the target `parking_availabilities` row with `SELECT ... FOR UPDATE`.
2. Verifies the availability is still open, not expired, not owned by the applicant, and tied to an active spot.
3. Checks for an existing application by the same applicant.
4. Inserts the pending application.
5. Converts a duplicate insert race into the existing `ParkingApplicationDuplicateError`.
6. Caller commits or rolls back the transaction.

## Critical Invariants

- At most one active reservation exists per availability.
- Exactly one application is selected for an assigned availability.
- A successful automatic assignment writes one assignment audit log for the availability.
- Duplicate applications by the same employee for the same availability are rejected deterministically.
- Concurrent applications from different employees are retained.
- Application creation overlapping with assignment does not leave pending orphan applications on an assigned availability.
- Raw database `IntegrityError` exceptions do not escape assignment/application service boundaries in the tested flows.
- Independent availabilities can be assigned concurrently.

## Defects Found and Fixes

### Application Creation Versus Assignment Race

Review of the pre-change application path showed that application creation read an availability without taking the same row lock used by assignment. That allowed this possible interleaving:

1. Application creation reads an open availability.
2. Assignment locks and assigns the availability.
3. Application creation inserts a new pending application after assignment candidate selection.

Fix:

- `ParkingApplicationService.apply_for_availability` now loads the availability through `get_by_id_for_update`.
- Duplicate insert races are converted to `ParkingApplicationDuplicateError`.
- No schema migration was required because the existing uniqueness constraints remain sufficient after the row-lock ordering fix.

## Test Coverage Added

New marked test suite:

- `backend/tests/postgres_concurrency/test_assignment_application_concurrency.py`

Marker:

- `postgres_concurrency`

Safety behavior:

- Tests require `POSTGRES_CONCURRENCY_DATABASE_URL`.
- Tests skip when that variable is not set.
- Tests fail if the URL is not PostgreSQL.
- Tests fail if the database name does not contain a disposable/test-oriented fragment such as `concurrency`, `test`, `tmp`, `temporary`, or `disposable`.
- Each test truncates model tables before and after execution.
- Worker sessions use separate database sessions/connections.
- Worker coordination uses barriers/events with bounded timeouts.
- Worker exceptions are collected and surfaced by the parent test.

Run command:

```powershell
$env:POSTGRES_CONCURRENCY_DATABASE_URL='postgresql+psycopg://parking_app:parking_app@localhost:55432/parking_app_concurrency'
$env:PYTHONPATH='backend;backend\.test-deps'
& 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' `
  -m pytest -c backend/pyproject.toml -m postgres_concurrency backend/tests/postgres_concurrency -q
```

Result:

- `7 passed`.

## Verification Results

Docker Compose config:

- Command: `docker-compose config`.
- Result: passed. Docker emitted a local client-config access warning, but Compose rendered a valid configuration.
- Note: expanded config output was not copied into this document because it can include local `.env` values.

Disposable PostgreSQL startup:

- Command: `docker-compose -p parkingappconcurrencyphase1 up -d db` with `POSTGRES_DB=parking_app_concurrency`, `POSTGRES_PORT=55432`.
- Result: project, network, and disposable volume created; PostgreSQL container reached healthy state.

Migration:

- Command: backend Alembic `upgrade head` with `DATABASE_URL=postgresql+psycopg://parking_app:parking_app@localhost:55432/parking_app_concurrency`.
- Result: migrations applied from `0001` through `0010`.

Focused PostgreSQL concurrency tests:

- Command: `pytest -c backend/pyproject.toml -m postgres_concurrency backend/tests/postgres_concurrency -q`.
- Result: `7 passed`.

Existing focused assignment/application tests:

- Command: from `backend`, `pytest tests/test_parking_application_service.py tests/test_parking_applications_api.py tests/test_parking_reservation_assignment_service.py tests/test_parking_assignment_scheduler.py -q`.
- Result: passed with one existing Starlette deprecation warning.

Full backend tests:

- Command: from `backend`, `pytest -q` with `POSTGRES_CONCURRENCY_DATABASE_URL` unset.
- Result: passed; PostgreSQL concurrency tests skipped as intended; one existing Starlette deprecation warning.

Compile check:

- Command: from `backend`, `python -m compileall app tests\postgres_concurrency`.
- Result: passed.

Alembic checks:

- Command: `alembic -c alembic.ini heads`.
- Result: `0010 (head)`.
- Command: `alembic -c alembic.ini history`.
- Result: linear history from `0001` through `0010`.
- Command: `alembic -c alembic.ini current` against disposable PostgreSQL.
- Result: `0010 (head)`.

Dependency audit:

- Command: `python -m pip_audit --cache-dir C:\tmp\pip-audit-cache -r requirements.txt -r requirements-dev.txt`.
- Result: `No known vulnerabilities found`.

Final disposable database check:

- Command: `psql` query for active reservations, pending applications, and Alembic version.
- Result: `active_reservations=0`, `pending_applications=0`, `alembic_version=0010`.

Cleanup:

- Command: `docker-compose -p parkingappconcurrencyphase1 down -v`.
- Result: disposable container, network, and volume removed.
- Command: `docker-compose -p parkingappconcurrencyphase1 ps`.
- Result: no remaining disposable services.

## Known Limitations

- This phase validates concurrency correctness, not throughput capacity.
- The tests intentionally do not cover cancellation, reassignment, admin override, or replacement override flows.
- No connection-pool tuning was performed.
- No new database migration was added.
- The normal full backend suite skips PostgreSQL concurrency tests unless `POSTGRES_CONCURRENCY_DATABASE_URL` is set.

## Phase 2 - Cancellation, Reassignment, and Override Concurrency

Status: READY

QA date: 2026-06-21

Environment:

- Local Windows development machine with Docker Desktop.
- Disposable Compose project: `parkingappconcurrencyphase2`.
- Disposable PostgreSQL database: `parking_app_concurrency`.
- Disposable PostgreSQL volume: `parkingappconcurrencyphase2_postgres_data`, removed after verification.
- Normal development PostgreSQL volume was not used.
- Alembic revision verified at `0010 (head)`.

Scope:

Phase 2 covered deterministic PostgreSQL concurrency tests for:

- Two admin cancellations for the same active reservation.
- Employee cancellation racing admin cancellation for the same active reservation.
- Cancellation that started before replacement override.
- Cancellation followed by reassignment.
- Two reassignment attempts for the same cancelled availability.
- Reassignment racing direct assignment.
- Reassignment racing admin manual override.
- Two admin manual overrides for the same availability.
- Admin manual override racing direct assignment.
- Two application-id replacement overrides for the same original reservation.
- Two applicant-id replacement overrides for the same original reservation.
- Repeated identical applicant-id replacement override.
- Application-id and applicant-id replacement overrides for the same original reservation.
- Replacement override racing cancellation.

Out of scope for this phase:

- General load-test harness.
- Throughput or latency tuning.
- Frontend browser QA.
- New schema or product functionality.
- Scheduled production execution changes.

### Invariants Validated

The Phase 2 tests validated that concurrent cancellation, reassignment, manual override, and replacement override paths preserve these invariants:

- At most one active reservation exists for an availability.
- A stale cancellation that began before a replacement does not cancel the replacement winner.
- Concurrent replacements targeting the same original reservation do not silently use last-write-wins semantics.
- A cancelled availability is assigned at most once when reassignment, direct assignment, or manual override race.
- Application states do not leave duplicate selected applications for the same availability.
- Missing, inactive, or already changed reservation state is handled as controlled service failure instead of uncontrolled database corruption.
- PostgreSQL row-locking behavior is exercised with separate database sessions and bounded worker timeouts.

### Defects Found and Fixes

Cancellation versus replacement:

- Defect: a cancellation that loaded the original active reservation before a concurrent replacement could wait on the availability lock, then cancel the newly replaced active reservation after the replacement committed.
- Fix: `ParkingReservationCancellationService` now records a scalar reservation identity snapshot before waiting on locks and raises a controlled `ParkingReservationCancellationIntegrityError` if the active reservation identity changed while the cancellation waited.

Concurrent replacement overrides:

- Defect: concurrent replacement overrides could both snapshot the same original active reservation before lock contention and then silently overwrite each other by cancelling/replacing the current active reservation after waiting.
- Fix: `AdminReservationOverrideService.replace_existing_reservation` now records the original active reservation identity before waiting on the availability lock and raises a controlled `AdminReservationOverrideIntegrityError` if the active reservation changed before the replacement proceeds.

No Alembic migration was required because both fixes are transaction/locking behavior changes in service code.

### Verification

Docker Compose config:

- Command: `docker-compose config`.
- Result: passed. Docker emitted a local client-config access warning, but Compose rendered a valid configuration.
- Note: expanded config output was not copied into this document because it can include local `.env` values.

Disposable PostgreSQL startup:

- Command: `docker-compose -p parkingappconcurrencyphase2 up -d db` with `POSTGRES_DB=parking_app_concurrency`, `POSTGRES_PORT=55432`.
- Result: project, network, and disposable volume created; PostgreSQL container reached healthy state.

Migration:

- Command: backend Alembic `upgrade head` with `DATABASE_URL=postgresql+psycopg://parking_app:parking_app@localhost:55432/parking_app_concurrency`.
- Result: migrations applied from `0001` through `0010`.

Focused Phase 2 PostgreSQL concurrency tests:

- Command: from `backend`, `pytest tests/postgres_concurrency/test_cancellation_reassignment_override_concurrency.py -q` with `POSTGRES_CONCURRENCY_DATABASE_URL` pointing at the disposable PostgreSQL database.
- Result: `14 passed`.

Full PostgreSQL concurrency suite:

- Command: from `backend`, `pytest tests/postgres_concurrency -q` with `POSTGRES_CONCURRENCY_DATABASE_URL` pointing at the disposable PostgreSQL database.
- Result: `21 passed`.

Focused cancellation/reassignment/override regression tests:

- Command: from `backend`, `pytest tests/test_parking_reservation_cancellation_service.py tests/test_parking_reservation_cancellations_api.py tests/test_parking_reassignment_service.py tests/test_parking_reassignment_api.py tests/test_admin_reservation_override_service.py tests/test_admin_reservation_overrides_api.py tests/test_admin_reservation_replacement_service.py tests/test_admin_reservation_replacements_api.py tests/test_parking_application_service.py tests/test_parking_applications_api.py tests/test_parking_reservation_assignment_service.py tests/test_parking_assignment_scheduler.py -q`.
- Result: passed with one existing Starlette deprecation warning.

Full backend tests:

- Command: from `backend`, `pytest -q` with `POSTGRES_CONCURRENCY_DATABASE_URL` unset.
- Result: passed; PostgreSQL concurrency tests skipped as intended; one existing Starlette deprecation warning.

Compile check:

- Command: from `backend`, `python -m compileall app tests\postgres_concurrency`.
- Result: passed.

Alembic checks:

- Command: `alembic -c alembic.ini heads`.
- Result: `0010 (head)`.
- Command: `alembic -c alembic.ini history`.
- Result: linear history from `0001` through `0010`.
- Command: `alembic -c alembic.ini current` against disposable PostgreSQL.
- Result: `0010 (head)`.

Dependency audit:

- Command: `python -m pip_audit --cache-dir C:\tmp\pip-audit-cache -r requirements.txt -r requirements-dev.txt`.
- Result: `No known vulnerabilities found`.

Final disposable database check:

- Command: `psql` query for active reservations, pending applications, and Alembic version.
- Result: `active_reservations=0`, `pending_applications=0`, `alembic_version=0010`.

Disposable PostgreSQL logs:

- Command: inspected disposable database logs for deadlocks, serialization failures, lock timeouts, uncontrolled integrity errors, and secret leakage.
- Result: no matching error conditions found.

Cleanup:

- Command: `docker-compose -p parkingappconcurrencyphase2 down -v`.
- Result: disposable container, network, and volume removed.
- Command: `docker-compose -p parkingappconcurrencyphase2 ps`.
- Result: no remaining disposable services.

Skip behavior:

- Command: from `backend`, `pytest tests/postgres_concurrency -q` with `POSTGRES_CONCURRENCY_DATABASE_URL` unset.
- Result: `21 skipped`.

## Known Limitations

- This phase validates correctness under deterministic races, not throughput capacity.
- It does not include a general API load harness, moderate load profile, stress profile, or connection-pool tuning.
- It does not validate frontend behavior.
- The normal full backend suite intentionally skips PostgreSQL concurrency tests unless `POSTGRES_CONCURRENCY_DATABASE_URL` is provided.

## Phase 3A - Bounded API Smoke Load Validation

Status: READY

QA date: 2026-06-22

Environment:

- Local Windows development machine with Docker Desktop.
- Disposable Compose project: `parkingapploadphase3a`.
- Disposable PostgreSQL database for smoke run: `parking_app_load_validation`.
- Disposable PostgreSQL database for concurrency regression: `parking_app_concurrency`.
- Disposable PostgreSQL volume: `parkingapploadphase3a_postgres_data`, removed after verification.
- Normal development PostgreSQL volume was not used.
- Alembic revision verified at `0010 (head)`.

### Harness Architecture

Phase 3A adds `python -m app.commands.run_load_validation --profile smoke`.

The command is import-safe and runs a bounded API-level smoke profile against an already running backend API. It uses the Python standard library HTTP client so it works inside the existing backend Docker image without adding a runtime dependency.

Supported command options:

- `--target-base-url`
- `--seed`
- `--concurrency`
- `--iterations`
- `--request-timeout`
- `--report-path`
- `--markdown-report-path`
- `--no-cleanup`
- `--allow-non-local-target`
- `--admin-identifier-env`
- `--admin-password-env`

Admin credentials are read from environment variable names, defaulting to `LOAD_VALIDATION_ADMIN_IDENTIFIER` and `LOAD_VALIDATION_ADMIN_PASSWORD`. Credential values are never written to the report.

### Safety Limits

- Only the `smoke` profile is implemented in Phase 3A.
- Smoke concurrency is bounded to 5-10 workers.
- Smoke iterations are bounded to 1-3.
- Per-request timeout is bounded to 0.1-30 seconds.
- Non-local targets are refused unless `--allow-non-local-target` is explicitly set.
- Target URLs containing credentials are rejected.
- Reports are sanitized and do not include passwords, JWTs, bearer tokens, emails, full database URLs, or free-text reasons.
- Cleanup is enabled by default and removes only tracked disposable IDs created by the run.

### Smoke Profile

The smoke profile creates a small disposable dataset and exercises these MVP API flows:

- admin login and `/auth/me`,
- owner and employee login,
- team, user, and parking spot setup,
- availability listing,
- concurrent application creation,
- duplicate application conflict classification,
- owner assignment execution,
- reservation reads,
- employee cancellation,
- reassignment after cancellation,
- admin manual override,
- admin replacement override,
- admin application/reservation/audit reads,
- admin report and CSV endpoints.

Expected domain conflicts, such as a duplicate application returning `409`, are counted separately from invariant failures.

### Connection Pool Configuration

Backend and scheduler now use these bounded settings:

- `DB_POOL_SIZE`, default `5`
- `DB_MAX_OVERFLOW`, default `5`
- `DB_POOL_TIMEOUT_SECONDS`, default `30`
- `DB_POOL_RECYCLE_SECONDS`, default `1800`
- `DB_POOL_PRE_PING`, default `true`

The engine receives these settings for PostgreSQL URLs. Queue-pool-only options are skipped for SQLite-compatible test URLs.

### Report Format

The sanitized JSON report includes:

- profile,
- random seed,
- UTC start/end timestamps,
- duration,
- dataset sizes,
- concurrency and iterations,
- request counts by classification and operation,
- latency p50/p95/p99,
- throughput,
- pool configuration,
- invariant results,
- cleanup result,
- completion classification.

Saved Phase 3A artifacts:

- `resources/docs/load_validation_phase3a_smoke_report.json`
- `resources/docs/load_validation_phase3a_smoke_report.md`

### Invariant Checks

The smoke run verifies:

- no more than one active reservation per availability,
- no more than one selected application per availability,
- no forbidden duplicate applications,
- assigned availability and active reservation states agree,
- cancellation/replacement history remains coherent,
- successful assignment/reassignment/override actions have expected audit records,
- no misleading success audit exists after the expected failed duplicate action,
- no orphan references exist.

### Verification

Compose config:

- Command: `docker-compose -p parkingapploadphase3a config --quiet`.
- Result: passed with no expanded config output copied.

Backend Docker build:

- Command: `docker-compose -p parkingapploadphase3a build backend`.
- Result: passed.

Disposable Docker startup:

- Command: `docker-compose -p parkingapploadphase3a up -d db backend` with disposable database and host ports.
- Result: PostgreSQL reached healthy state and backend started.

Migration and admin seed:

- Command: `docker-compose -p parkingapploadphase3a exec -T backend alembic -c alembic.ini upgrade head`.
- Result: migrations applied through `0010`.
- Command: `docker-compose -p parkingapploadphase3a exec -T backend alembic -c alembic.ini current`.
- Result: `0010 (head)`.
- Command: disposable local admin seed with `SEED_ADMIN_*` environment variables.
- Result: passed after replacing a rejected `.invalid` email with a validator-compatible `example.com` email. Disposable password value was not recorded.

Smoke profile:

- Command: `docker-compose -p parkingapploadphase3a exec -T backend python -m app.commands.run_load_validation --profile smoke --target-base-url http://localhost:8000 --seed 20260622 --concurrency 5 --iterations 1 --request-timeout 10 --report-path /tmp/phase3a-smoke.json --markdown-report-path /tmp/phase3a-smoke.md`.
- Result: `load validation READY`.
- Requests: `54` total, `53` success, `1` expected domain conflict.
- Latency: p50 `47.023 ms`, p95 `254.122 ms`, p99 `333.824 ms`.
- Invariants: all passed.
- Cleanup: deleted disposable teams, users, parking spot, availabilities, applications, reservations, and audit logs.

Post-cleanup database check:

- Command: disposable PostgreSQL query for load-validation users, disposable availabilities, active reservations, and Alembic version.
- Result: `disposable_users=0`, `disposable_availabilities=0`, `active_reservations=0`, `alembic_version=0010`.

Log inspection:

- Command: scanned disposable backend/database logs for deadlocks, serialization failures, lock timeouts, tracebacks, internal server errors, bearer tokens, access tokens, credential URLs, and the disposable admin password.
- Result: no matches.

Phase 1/2 concurrency regression:

- Command: created disposable database `parking_app_concurrency` inside the same temporary PostgreSQL container and migrated it to `0010`.
- Command: from `backend`, `pytest tests/postgres_concurrency -q` with `POSTGRES_CONCURRENCY_DATABASE_URL` pointing at the disposable concurrency database.
- Result: `21 passed`.

Regression checks:

- Command: from `backend`, `pytest tests/test_database_pool_config.py tests/test_infrastructure_files.py tests/test_load_validation_harness.py -q`.
- Result: passed.
- Command: from `backend`, `pytest -q` with `POSTGRES_CONCURRENCY_DATABASE_URL` unset.
- Result: passed; PostgreSQL concurrency tests skipped as intended; one existing Starlette deprecation warning.
- Command: from `backend`, `python -m compileall app tests`.
- Result: passed.
- Command: `alembic -c alembic.ini heads`.
- Result: `0010 (head)`.
- Command: `alembic -c alembic.ini history`.
- Result: linear history from `0001` through `0010`.
- Command: `alembic -c alembic.ini current` against disposable PostgreSQL.
- Result: `0010 (head)`.
- Command: `python -m pip_audit --cache-dir C:\tmp\pip-audit-cache -r requirements.txt -r requirements-dev.txt`.
- Result: `No known vulnerabilities found`.

Cleanup:

- Command: `docker-compose -p parkingapploadphase3a down -v`.
- Result: disposable containers, network, and `parkingapploadphase3a_postgres_data` volume removed.
- Command: `docker-compose -p parkingapploadphase3a ps`.
- Result: no remaining disposable services.

### Known Limitations

- Phase 3A is a smoke-level API load validation, not a throughput benchmark.
- It does not implement the moderate profile, stress profile, distributed load testing, or SLA/SLO claims.
- It does not collect Prometheus before/after metric deltas.
- It does not tune the connection pool beyond adding bounded, configurable settings.
- It does not validate frontend browser behavior.

## Phase 3B Moderate Load Validation

Phase 3B adds a bounded moderate API profile, Prometheus metric snapshots and deltas, PostgreSQL aggregate diagnostics, and a deliberate connection-pool saturation/recovery diagnostic.

This phase remains a local hardening check. It is not a stress test, production capacity test, or SLA/SLO benchmark.

### Moderate Profile Safety Bounds

The moderate profile must be explicitly confirmed:

```powershell
$env:LOAD_VALIDATION_ADMIN_IDENTIFIER = "local_admin"
$env:LOAD_VALIDATION_ADMIN_PASSWORD = Read-Host "Load validation admin password"

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

The command refuses unsafe moderate settings:

- `--confirm-moderate` is required.
- concurrency must stay between `25` and `50`.
- iterations must stay between `1` and `2`.
- global timeout must stay between `30` and `600` seconds.
- non-local API targets remain refused unless explicitly overridden.
- credential-bearing target URLs remain rejected.

### Additional Phase 3B Report Data

The JSON report schema now includes:

- latency min, max, average, p50, p95, and p99,
- backend Prometheus baseline/final snapshots and deltas,
- scheduler Prometheus baseline/final snapshots and deltas when a scheduler metrics URL is supplied,
- PostgreSQL sampled aggregate diagnostics,
- deliberate pool saturation/recovery diagnostic result,
- global timeout setting,
- report schema version.

Saved Phase 3B artifacts:

- `resources/docs/load_validation_phase3b_smoke_baseline_report.json`
- `resources/docs/load_validation_phase3b_smoke_baseline_report.md`
- `resources/docs/load_validation_phase3b_moderate_report.json`
- `resources/docs/load_validation_phase3b_moderate_report.md`
- `resources/docs/load_validation_phase3b_pool_report.json`
- `resources/docs/load_validation_phase3b_pool_report.md`

### Final Local Verification Result

The final Phase 3B run used disposable Docker project `parkingapploadphase3b` and PostgreSQL database `parking_app_load_validation_b`.

Clean startup order:

1. `docker-compose -p parkingapploadphase3b up -d db backend`
2. `docker-compose -p parkingapploadphase3b exec -T backend alembic -c alembic.ini upgrade head`
3. disposable local admin seed with `SEED_ADMIN_*` environment variables
4. `docker-compose -p parkingapploadphase3b --profile monitoring up -d assignment-scheduler prometheus`

Smoke baseline:

- Command: `python -m app.commands.run_load_validation --profile smoke --target-base-url http://localhost:8000 --seed 2026062205 --concurrency 5 --iterations 1 --request-timeout 10`.
- Result: `load validation READY`.

Moderate profile:

- Command: `python -m app.commands.run_load_validation --profile moderate --confirm-moderate --target-base-url http://localhost:8000 --scheduler-metrics-url http://assignment-scheduler:19101/metrics --seed 2026062206 --concurrency 25 --iterations 1 --request-timeout 15 --global-timeout 240`.
- Result: `load validation READY`.
- Requests: `284` total, `283` success, `1` expected domain conflict.
- Duration: `22.236` seconds.
- Throughput: `12.772` requests/second.
- Latency: p95 `358.833 ms`, p99 `470.241 ms`.
- Invariants: all passed.
- Cleanup: succeeded.
- PostgreSQL diagnostic samples: `46`.
- PostgreSQL deadlock delta: `0`.
- Pool diagnostic: expected timeout observed, pool recovery succeeded, checked out connections after recovery `0`.

Post-cleanup database check:

- Result: `disposable_users=0`, `disposable_teams=0`, `disposable_spots=0`, `disposable_availabilities=0`, `disposable_applications=0`, `active_reservations=0`, `alembic_version=0010`.

Log and report scans:

- Saved reports were scanned for disposable credential strings, emails, bearer tokens, access tokens, password/secret strings, and full PostgreSQL URLs.
- Clean-run backend, database, scheduler, and Prometheus logs were scanned for tracebacks, errors, deadlocks, serialization failures, lock timeouts, 500 responses, bearer/access tokens, credential URLs, and the disposable admin password.
- Result: no matches.

### Phase 3B Notes

- A first moderate dry run exposed a harness setup defect: the workload attempted to create a replacement candidate application through the public application endpoint after the availability was already assigned. The application correctly rejected that request. The harness now creates that one disposable pending setup row internally, then exercises the real admin replacement endpoint.
- The pool saturation diagnostic uses a separate one-connection SQLAlchemy engine. It intentionally expects one bounded pool timeout and then verifies pool recovery.
- PostgreSQL blocked-session samples during assignment/replacement windows are diagnostic observations, not failures. Invariant checks and deadlock deltas determine correctness for this bounded local profile.

## Next Hardening Direction

Recommended follow-up areas:

- frontend end-to-end smoke coverage,
- deployment runbooks and backup restore drills,
- production observability alert tuning,
- scheduled performance checks in a controlled non-production environment.
