# ParkingApp v1.0.0 MVP

**Tag:** v1.0.0-mvp

ParkingApp v1.0.0-mvp is the first MVP baseline for a company parking management application supporting administrators, employees, and parking owners.

## Summary

The release delivers the complete parking lifecycle: administrators configure teams, users, owned parking spots, operational records, overrides, and reports; parking owners publish availability from their own active spots; employees apply for availability and receive auditable reservations through scheduled assignment.

## Main Workflows

- Administrators manage teams, users, parking spots, applications, reservations, assignment audit logs, overrides, reports, and CSV exports.
- Parking owners publish and cancel availability using an owner-scoped spot selector with no manual Parking spot ID field.
- Employees browse available parking, apply or cancel, and review or cancel reservations.
- The assignment runner ranks due applications, creates reservations transactionally, and records decisions.
- Administrators can manually assign, replace, or cancel reservations with mandatory reasons and preserved history.
- Authenticated users receive role-specific navigation and Help content; the end-user guide includes generated workflow screenshots.

## Verification Status

- [x] Hosted backend quality passed.
- [x] Hosted PostgreSQL concurrency passed with 21 executed tests and no skips.
- [x] Hosted frontend tests and production build passed.
- [x] Hosted Docker Compose and bounded image validation passed.
- [x] Hosted Chromium six-flow MVP smoke passed.
- [x] Python and npm dependency audits passed.
- [x] Alembic graph is linear with one head at 0010.

The release baseline is merge commit cf041bea977020c9eef1de22be6485d1ac7c27ef before release-document preparation. Release documentation should be merged to main before the final tag is created.

## Security Notes

- JWT access tokens use PyJWT and configured secrets/algorithms; the vulnerable python-jose/ecdsa dependency chain was removed.
- Passwords are hashed and are not returned by read schemas.
- Authentication distinguishes 401 from authorization 403 without leaking credential details.
- Configurable CORS, request IDs, security headers, production secret-file examples, and TLS proxy groundwork are included.
- No production credentials, private keys, certificates, or bearer tokens are part of the release.

## Known Limitations

- No production deployment, Docker image publication, managed TLS certificate, or cloud environment is included.
- Production operators must configure secret management, scheduler orchestration, backups, monitoring, alerts, log shipping, and recovery testing.
- SSO/OIDC, email or push notifications, scheduled report delivery, and external observability integrations remain post-MVP work.
- Docker Compose targets local and release-candidate validation; deployment-specific manual QA remains required.

## Upgrade And Deployment Notes

1. Provide environment-specific database and JWT secrets; do not use example defaults.
2. Build the backend and frontend from the tagged source.
3. Back up the target PostgreSQL database and verify the archive before migration.
4. Apply alembic -c alembic.ini upgrade head; expected head is 0010.
5. Start backend, frontend, scheduler, TLS, and monitoring components according to the target platform.
6. Verify health, readiness, metrics, CORS, security headers, login, assignment, and backup recovery in that environment.

This release does not perform or imply a production deployment.

## GitHub Release Draft

**Title:** ParkingApp v1.0.0 MVP
**Tag:** v1.0.0-mvp

ParkingApp v1.0.0-mvp is the first MVP baseline for a company parking management application supporting administrators, employees, and parking owners.

### Highlights

- Role-based admin, employee, and parking-owner workflows.
- Owner-scoped availability publishing without manual spot identifiers.
- Employee applications, deterministic scheduled assignment, reservations, and cancellations.
- Audited admin manual/replacement overrides and operational CSV reports.
- Docker Compose runtime, Help/user guide, backup/restore, observability, TLS, and secrets groundwork.
- PyJWT security remediation and passing dependency audits.

### Verification Checklist

- [x] Backend quality
- [x] PostgreSQL concurrency
- [x] Frontend quality and production build
- [x] Docker Compose and image validation
- [x] Chromium MVP smoke
- [x] Dependency audits
- [x] Alembic head 0010

### Known Limitations

- Production deployment and image publication are not included.
- Deployment-specific secrets, TLS certificates, backups, monitoring destinations, and scheduler orchestration must be supplied by operators.
- SSO/OIDC, notifications, scheduled reports, and external observability remain post-MVP work.

No production deployment is included in this release.

## Tag Preparation

After the release commit is merged to an up-to-date, clean main, verify that the tag does not exist and run:

```powershell
git tag -a v1.0.0-mvp -m "ParkingApp v1.0.0 MVP"
git push origin v1.0.0-mvp
```

Do not move or recreate the tag after publication.
