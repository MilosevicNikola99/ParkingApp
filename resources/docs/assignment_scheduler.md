# Assignment Scheduler

The assignment scheduler is a production-ready runner for due parking-availability assignment. It reuses the existing assignment service and ranking policy. It does not change fairness, same-team priority, override behavior, or the manual one-shot command.

## Commands

Manual one-shot assignment remains available:

```powershell
docker-compose exec -T backend python -m app.commands.assign_due_availabilities --limit 100
```

Run one protected scheduler cycle:

```powershell
docker-compose exec -T -e ASSIGNMENT_SCHEDULER_ENABLED=true backend python -m app.commands.run_assignment_scheduler --once
```

Run the continuous scheduler service through the optional Compose profile:

```powershell
docker-compose --profile scheduler up -d assignment-scheduler
```

Stop the scheduler service while preserving database data:

```powershell
docker-compose stop assignment-scheduler
docker-compose down
```

## Configuration

All scheduler settings are disabled/safe by default:

```text
ASSIGNMENT_SCHEDULER_ENABLED=false
ASSIGNMENT_SCHEDULER_INTERVAL_SECONDS=60
ASSIGNMENT_SCHEDULER_BATCH_LIMIT=100
ASSIGNMENT_SCHEDULER_LOCK_KEY=740730001
ASSIGNMENT_SCHEDULER_RUN_IMMEDIATELY=true
```

The API/backend container keeps `ASSIGNMENT_SCHEDULER_ENABLED=false`. The optional `assignment-scheduler` Compose service sets it to `true` because selecting the `scheduler` profile is the explicit enablement step.

Validation rules:

- `ASSIGNMENT_SCHEDULER_ENABLED` must be `true` before the long-running scheduler performs work.
- `ASSIGNMENT_SCHEDULER_INTERVAL_SECONDS` must be between `5` and `86400`.
- `ASSIGNMENT_SCHEDULER_BATCH_LIMIT` must be between `1` and `1000`.
- `ASSIGNMENT_SCHEDULER_LOCK_KEY` must be a positive PostgreSQL advisory-lock key.
- `ASSIGNMENT_SCHEDULER_RUN_IMMEDIATELY=true` runs the first cycle at startup; `false` waits one interval before the first cycle.

## Locking And Failure Behavior

Each scheduler cycle opens a database session and attempts `pg_try_advisory_lock` with `ASSIGNMENT_SCHEDULER_LOCK_KEY`.

- If the lock is acquired, the runner processes one existing due-assignment batch.
- If the lock is unavailable, the cycle is skipped and the process keeps running.
- The lock is released in a `finally` block after success or failure.
- Recoverable cycle exceptions are logged and do not stop the continuous process.
- `SIGTERM` and `SIGINT` request graceful shutdown. The runner exits after the current cycle or sleep interval is interrupted.

This advisory lock is process-wide for the configured PostgreSQL database and prevents two scheduler instances from running the same assignment batch at the same time. Assignment still keeps the existing row-level locking behavior for individual availability selection.

## Logging

The scheduler uses the existing structured logging setup. Cycle logs include:

- run/correlation ID,
- lock key and acquisition status,
- interval and batch limit,
- processed, assigned, skipped, failed, and issue counts,
- duration in milliseconds,
- error type for failed cycles.

Passwords, bearer tokens, request bodies, and user-sensitive fields are not logged by the scheduler.

## Metrics

When `METRICS_ENABLED=true`, the scheduler process starts an internal Prometheus metrics server on `SCHEDULER_METRICS_PORT` with path `/metrics`. In local Compose monitoring mode, Prometheus scrapes `assignment-scheduler:9101/metrics`.

Scheduler metrics:

- `parking_assignment_scheduler_cycles_total{result}` with `success`, `error`, and `lock_skipped`.
- `parking_assignment_scheduler_assignments_produced_total`.
- `parking_assignment_scheduler_cycle_duration_seconds_bucket{result,le}`.
- `parking_assignment_scheduler_last_success_timestamp_seconds`.
- `parking_assignment_scheduler_running_cycles`.
- `parking_assignment_scheduler_lock_skips_total`.

Metrics collection is defensive; a metrics recording failure is logged and does not stop scheduler execution.

## Local Verification

Recommended local verification sequence:

```powershell
docker-compose config
docker-compose build backend
docker-compose up -d db backend
docker-compose exec -T backend alembic -c alembic.ini upgrade head
docker-compose exec -T -e ASSIGNMENT_SCHEDULER_ENABLED=true backend python -m app.commands.run_assignment_scheduler --once
docker-compose --profile scheduler up -d assignment-scheduler
docker-compose --profile monitoring up -d assignment-scheduler prometheus grafana
docker-compose logs assignment-scheduler
docker-compose down
```

For production, run the scheduler as a separate service or worker process using the same backend image after migrations have been applied.
