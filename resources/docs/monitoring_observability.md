# Monitoring and Observability

This runbook documents the MVP observability baseline for the Parking Management App. It covers health endpoints, Prometheus metrics, scheduler visibility, log correlation, local monitoring Compose usage, and production hardening notes.

## Endpoints

### Liveness

`GET /health/live`

- Confirms the FastAPI process can respond.
- Does not check PostgreSQL.
- Returns `200` quickly when the process is alive.
- Response fields: `status`, `service`, `environment`.

### Readiness

`GET /health/ready`

- Confirms the service can accept traffic.
- Runs a lightweight PostgreSQL `SELECT 1` check with `READINESS_DATABASE_TIMEOUT_SECONDS`.
- Returns `200` with `status=ready` when dependencies are available.
- Returns `503` with `status=not_ready` when PostgreSQL is unavailable or times out.
- Client responses do not include credentials, database URLs, exception details, host paths, or stack traces.

Deployment should still run Alembic `current`/`upgrade head` as a startup or rollout check. Readiness does not run Alembic history because that would be too expensive for every probe.

### Compatibility Health

`GET /health`

- Remains a compatibility alias for the simple liveness response.
- Existing smoke checks can continue using this endpoint.

### Metrics

`GET /metrics`

- Exports Prometheus text format.
- The backend metrics endpoint is intended for internal monitoring access.
- Production TLS proxy blocks public `/metrics` and `/api/metrics` by default.

## Metric Inventory

HTTP metrics:

- `parking_http_requests_total{method,route,status_code,status_class}`
- `parking_http_request_duration_seconds_bucket{method,route,status_code,status_class,le}`
- `parking_http_requests_in_progress{method}`
- `parking_unhandled_exceptions_total{exception_type,route}`
- `parking_auth_failures_total{reason}`

Readiness metrics:

- `parking_readiness_dependency_status{dependency}` where `1` is healthy and `0` is unhealthy.

Scheduler metrics:

- `parking_assignment_scheduler_cycles_total{result}` with `success`, `error`, and `lock_skipped`.
- `parking_assignment_scheduler_assignments_produced_total`
- `parking_assignment_scheduler_cycle_duration_seconds_bucket{result,le}`
- `parking_assignment_scheduler_last_success_timestamp_seconds`
- `parking_assignment_scheduler_running_cycles`
- `parking_assignment_scheduler_lock_skips_total`

The Prometheus client also exports Python/process runtime metrics. Treat those as process-level operational signals, not product metrics.

## Label Policy

Metric labels must stay low-cardinality and non-sensitive.

Allowed labels include:

- HTTP method,
- normalized route template,
- response status code or status class,
- scheduler result,
- dependency name,
- broad exception type,
- broad auth failure reason.

Do not use these values as labels:

- usernames,
- emails,
- user IDs,
- request IDs,
- raw URLs or URL segments with IDs,
- free-text reasons,
- request bodies,
- authorization headers,
- secret paths,
- database URLs.

Unmatched routes use `route="<unmatched>"` instead of the raw request path.

## Local Monitoring Stack

Start the application and monitoring profile:

```powershell
docker-compose config
docker-compose build backend frontend
docker-compose up -d db backend frontend
docker-compose exec -T backend alembic -c alembic.ini upgrade head
docker-compose --profile monitoring up -d assignment-scheduler prometheus grafana
```

Local URLs:

- Backend liveness: `http://localhost:8000/health/live`
- Backend readiness: `http://localhost:8000/health/ready`
- Backend metrics: `http://localhost:8000/metrics`
- Prometheus: `http://127.0.0.1:9090`
- Grafana: `http://127.0.0.1:3000`

Local monitoring ports are bound to `127.0.0.1` by default:

```text
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000
```

Grafana local defaults:

```text
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=local-grafana-admin
```

These are local-only defaults. Do not use them for production.

Stop services while preserving the normal PostgreSQL volume:

```powershell
docker-compose down
```

Remove local monitoring/application volumes only when intentionally discarding local data:

```powershell
docker-compose down -v
```

## Prometheus Configuration

The local Prometheus config is `deploy/prometheus/prometheus.yml`.

Scrape jobs:

- `parking-backend` scrapes `backend:8000/metrics`.
- `parking-assignment-scheduler` scrapes `assignment-scheduler:9101/metrics`.

The assignment scheduler starts a lightweight metrics server on `SCHEDULER_METRICS_PORT` when `METRICS_ENABLED=true`. This lets Prometheus observe the scheduler process separately from the API process.

## Sample PromQL

Total request rate:

```promql
sum(rate(parking_http_requests_total[5m]))
```

5xx request rate:

```promql
sum(rate(parking_http_requests_total{status_class="5xx"}[5m]))
```

p95 request latency:

```promql
histogram_quantile(0.95, sum(rate(parking_http_request_duration_seconds_bucket[5m])) by (le))
```

Readiness availability:

```promql
avg_over_time(parking_readiness_dependency_status{dependency="database"}[5m])
```

Scheduler failure rate:

```promql
sum(rate(parking_assignment_scheduler_cycles_total{result="error"}[10m]))
```

Time since last successful scheduler cycle:

```promql
time() - parking_assignment_scheduler_last_success_timestamp_seconds
```

Assignments produced over one hour:

```promql
increase(parking_assignment_scheduler_assignments_produced_total[1h])
```

Scheduler lock skips over 15 minutes:

```promql
increase(parking_assignment_scheduler_lock_skips_total[15m])
```

## Alert Rule Examples

Example rules are in `deploy/prometheus/alert_rules.yml`:

- `BackendNotReady`
- `HighServerErrorRate`
- `HighRequestLatency`
- `AssignmentSchedulerNoRecentSuccess`
- `AssignmentSchedulerCycleFailures`
- `PostgreSQLReadinessFailure`

Thresholds are examples and require production tuning. The scheduler freshness alert assumes a roughly 60 second scheduler interval and should be adjusted if `ASSIGNMENT_SCHEDULER_INTERVAL_SECONDS` changes.

No notification receiver is configured in this task. Production deployments should wire Alertmanager or the platform alerting service separately.

## Logs and Metrics Correlation

Structured logs already include request IDs for HTTP requests and run IDs for scheduler cycles. Metrics intentionally do not include request IDs because that would create high cardinality.

Recommended operator workflow:

1. Use Prometheus or Grafana to identify the metric spike, route template, status class, or scheduler result.
2. Search backend logs by event name, route template, status code, and time window.
3. Use `X-Request-ID` from a failing client response to find exact request logs.
4. For scheduler issues, search `assignment_scheduler_cycle_*` logs by run ID and time window.
5. For assignment outcomes, correlate scheduler logs with assignment audit logs in the application.

Safe event names include:

- `http_request_completed`
- `http_request_failed`
- `readiness_dependency_failed`
- `assignment_scheduler_cycle_started`
- `assignment_scheduler_cycle_completed`
- `assignment_scheduler_cycle_skipped_lock_unavailable`
- `assignment_scheduler_cycle_failed`
- `assignment_scheduler_metrics_server_started`

## Backup Observability

Backup scheduling is intentionally not implemented here. Current backup scripts generate metadata sidecars with timestamp, size, Alembic revision, and SHA-256 checksum.

Future production backup monitoring should publish:

- last successful backup timestamp,
- last successful verification timestamp,
- backup failure count,
- verification failure count,
- restore-drill age,
- backup size trend.

Those signals should be emitted by the external backup scheduler or platform job after running the existing backup and verification scripts.

## Load Validation Metrics

Phase 3A load validation produces sanitized client-side JSON and Markdown reports for the bounded smoke profile. The report includes request classifications, latency p50/p95/p99, throughput, pool configuration, invariant results, cleanup result, and completion classification.

Phase 3B adds a confirmed moderate profile with before/after Prometheus snapshots and deltas for backend metrics and, when supplied, assignment scheduler metrics. The report also includes PostgreSQL aggregate samples and a bounded connection-pool saturation/recovery diagnostic.

Saved Phase 3B reports:

- `resources/docs/load_validation_phase3b_smoke_baseline_report.json`
- `resources/docs/load_validation_phase3b_smoke_baseline_report.md`
- `resources/docs/load_validation_phase3b_moderate_report.json`
- `resources/docs/load_validation_phase3b_moderate_report.md`
- `resources/docs/load_validation_phase3b_pool_report.json`
- `resources/docs/load_validation_phase3b_pool_report.md`

The Phase 3B moderate report is still a local validation artifact. It must not be treated as a production capacity benchmark or SLA/SLO statement. Use the Prometheus deltas to confirm that expected routes, status classes, latency buckets, scheduler cycles, and assignment counters moved during the run.

## Multi-Process Limitations

The backend Dockerfile currently runs one Uvicorn worker:

```text
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The current Prometheus Python client setup is correct for a single process. If Gunicorn or multiple Uvicorn workers are introduced later, metrics will not be correct without Prometheus Python client multiprocess mode and a per-worker metrics directory. Do not scale backend workers until multiprocess metrics behavior is explicitly implemented and tested.

The assignment scheduler is a separate process and exposes its own metrics server on the internal Docker network.

## Security Notes

- Backend `/metrics` is intended for internal scraping.
- The production TLS proxy blocks `/metrics` and `/api/metrics`.
- Local Prometheus and Grafana bind to `127.0.0.1`.
- Grafana local defaults are not production credentials.
- Health responses reveal only minimal service, environment, status, and dependency state.
- Metrics must not contain PII, secrets, raw request paths, request bodies, bearer tokens, or request IDs.

## Troubleshooting

- Readiness returns `503`: check PostgreSQL health, database network connectivity, credentials, and migration status.
- Liveness succeeds but readiness fails: the API process is alive, but a dependency is unavailable.
- Prometheus target is down: check `docker-compose --profile monitoring ps`, Prometheus target URL, and service DNS names.
- Scheduler metrics are missing: confirm `assignment-scheduler` is running with `METRICS_ENABLED=true` and `SCHEDULER_METRICS_PORT=9101`.
- Grafana has no data: confirm the Prometheus datasource points to `http://prometheus:9090` and Prometheus targets are UP.
