# Changelog

All notable ParkingApp changes are documented in this file.

## [v1.0.0-mvp] - 2026-07-12

### Added

- Company parking management MVP for administrators, employees, and parking owners.
- Role-based JWT authentication and authorization for ADMIN, EMPLOYEE, and PARKING_OWNER users.
- Admin management of teams, users, parking spots, applications, reservations, assignment audit logs, overrides, and operational reports.
- Parking-owner availability publishing scoped to owned active parking spots, without manual Parking spot ID entry.
- Employee availability discovery, application, cancellation, reservation, and reservation-cancellation workflows.
- Scheduled due-availability assignment with deterministic ranking, fairness controls, PostgreSQL locking, and audit history.
- Admin manual assignment, replacement override, and cancellation flows with mandatory reasons and preserved audit history.
- CSV operational report exports, authenticated Help page, and illustrated end-user guide.
- Docker Compose local runtime for PostgreSQL, FastAPI, Vue/nginx, optional scheduler, and monitoring profiles.
- Monitoring and observability groundwork, PostgreSQL backup/verification/restore scripts, and production secrets/TLS groundwork.
- Hosted GitHub Actions pipelines for backend, PostgreSQL concurrency, frontend, Compose/image, dependency, and Chromium Playwright verification.

### Changed

- Frontend package version set to 1.0.0-mvp as the release version reference.
- Parking-owner publishing derives eligible parking spots from authenticated ownership rather than accepting raw identifiers.
- JWT implementation uses PyJWT while preserving token claims and authentication behavior.

### Security

- Password hashing, bearer-token validation, active-user checks, role dependencies, configurable CORS, request IDs, and security headers are enabled.
- Vulnerable python-jose/ecdsa dependencies were replaced with PyJWT.
- Python and npm dependency audits pass without ignored findings.
- Production secret-file and TLS proxy groundwork is documented; real deployment secrets are not included.

### Verification

- Hosted backend quality, PostgreSQL concurrency, frontend quality, Docker Compose/image validation, and Chromium MVP smoke workflows pass.
- PostgreSQL concurrency verification executes all 21 marked tests without skips.
- Alembic has one linear head at 0010.
- The six-flow browser smoke validates admin setup, owner publishing, employee application/assignment, overrides, protected navigation, and Help access.

### Known Limitations

- This release does not include a production deployment, hosted environment, managed TLS certificates, or production secrets.
- Operators must provide production scheduling/orchestration, backups, monitoring destinations, alerting, and recovery procedures.
- SSO/OIDC, notifications, scheduled report delivery, and external observability integrations are not included.
- Docker Compose is the supported local runtime; exploratory manual QA remains recommended for deployment-specific environments.
