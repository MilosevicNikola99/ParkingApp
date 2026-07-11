# PostgreSQL Load Validation Smoke Report

- Profile: `smoke`
- Completion: `READY`
- Random seed: `20260622`
- Duration seconds: `5.565`
- Concurrency: `5`
- Iterations: `1`
- Total requests: `54`
- Latency p50/p95/p99 ms: `47.023` / `254.122` / `333.824`

## Invariants

- `active_reservation_uniqueness`: passed
- `selected_application_uniqueness`: passed
- `duplicate_application_uniqueness`: passed
- `availability_reservation_state_agreement`: passed
- `cancellation_replacement_history_coherence`: passed
- `expected_success_audit_records`: passed
- `orphan_reference_absence`: passed
