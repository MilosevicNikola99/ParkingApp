# Manual QA Checklist

Use this checklist for release-candidate browser validation after automated tests and Docker smoke checks pass.

## Preconditions

- [ ] `docker-compose up -d db backend frontend` is running.
- [ ] Alembic migration is applied and `alembic current` reports head `0010`.
- [ ] A local admin user is available through the safe seed command.
- [ ] Test users exist for `ADMIN`, `EMPLOYEE`, and `PARKING_OWNER`.
- [ ] At least one team and at least one parking spot exist for workflow testing.

## Automated Browser Smoke

Run the Playwright lifecycle before the remaining exploratory checks:

```powershell
cd frontend
npx.cmd playwright install chromium
cd ..
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_e2e_smoke.ps1
```

The automated suite covers:

- admin login and disposable team, owner, employee A, employee B, and parking-spot creation through the UI;
- owner availability publication and own-list verification;
- employee applications, the real one-shot assignment command, and reservation verification;
- Applicant ID replacement plus blank reason, unknown applicant, and current-reserved-user errors;
- post-replacement employee, reservation-history, audit-log, and report checks;
- unauthenticated/admin-route redirects, role-specific navigation, desktop flow, and a `390x844` override-form smoke check.

Selectors use accessible labels, roles, headings, regions, and run-specific record text. Add `data-testid` only when no stable accessible selector exists. Failure screenshots, video, and traces are local artifacts under `frontend/test-results`; they are gitignored and must not be committed because traces can contain disposable credentials.

If Docker reports named-pipe access errors, run from a Windows account with Docker Desktop access, confirm membership in `docker-users`, restart the session if membership changed, and retry. HTTP-only checks are not a substitute for this browser suite.

## Authentication

- [ ] Login succeeds with valid username credentials and returns the dashboard.
- [ ] Login succeeds with valid email credentials.
- [ ] Wrong password shows a generic failure and does not reveal whether the account exists.
- [ ] Unknown username or email shows the same generic failure.
- [ ] Logout clears the local auth state and returns to login.
- [ ] Direct navigation to a protected route without a token redirects or blocks access.
- [ ] Expired or malformed token results in an unauthenticated state.

## Employee Workflows

- [ ] Employee can open the dashboard and see employee-relevant navigation only.
- [ ] Employee can view open parking availabilities.
- [ ] Employee can submit an application for an eligible availability.
- [ ] Duplicate application attempt is blocked with a clear error.
- [ ] Employee cannot apply to their own spot availability.
- [ ] Employee can view their applications and statuses.
- [ ] Employee can cancel a pending application.
- [ ] Employee can view assigned reservations.
- [ ] Employee can cancel their own active reservation where the workflow allows it.

## Parking Owner Workflows

- [ ] Parking owner can open the dashboard and see owner-relevant navigation only.
- [ ] Owner with one active assigned spot sees that spot automatically and no raw spot ID input.
- [ ] Owner with multiple active assigned spots can select only from their own spots.
- [ ] Owner with no active assigned spot sees contact-admin guidance and cannot publish.
- [ ] Owner can publish a new availability without typing a parking spot ID.
- [ ] Owner cannot publish for another owner's or an inactive parking spot through a direct API request.
- [ ] Overlapping availability creation is blocked.
- [ ] Owner can view submitted applications for their availability where expected.
- [ ] Owner can cancel an availability where the workflow allows it.
- [ ] Due availability assignment can be triggered through the backend command.
- [ ] Assignment creates the expected reservation and audit entry.

## Admin Workflows

- [ ] Admin can access admin navigation and admin-only routes.
- [ ] Non-admin users cannot access admin routes.
- [ ] Admin can create, edit, and deactivate users.
- [ ] Admin can create and update teams.
- [ ] Admin can create and update parking spots.
- [ ] Admin can view applications, reservations, assignment history, and audit logs.
- [ ] Admin can manually assign a reservation.
- [ ] Admin can replace an active reservation through override workflow.
- [ ] Admin can cancel an active reservation through override workflow.
- [ ] Override actions create audit log entries with actor and reason data.
- [ ] Admin report views load summary, top users, spot usage, audit activity, and CSV exports.

## Frontend Routing And Layout

- [ ] Refreshing `/login` returns the login page.
- [ ] Refreshing `/dashboard` returns the Vue application, not an nginx 404.
- [ ] Refreshing `/availabilities` returns the Vue application, not an nginx 404.
- [ ] Refreshing `/admin` returns the Vue application, not an nginx 404.
- [ ] Sidebar collapse and expand works on desktop and remains clear for keyboard users.
- [ ] Sidebar collapsed state persists after page reload in the same browser.
- [ ] Help page is available after login and shows Employee, Parking owner, and Administrator guidance.
- [ ] Main workflows fit at desktop width without overlapping controls.
- [ ] Main workflows fit at mobile width without clipped buttons or overlapping text.
- [ ] Loading, empty, success, warning, and error states are readable.

## API And Security

- [ ] `GET /health` returns OK.
- [ ] API responses include a request ID header.
- [ ] Security headers are present on backend responses.
- [ ] CORS preflight succeeds for the configured frontend origin.
- [ ] CORS preflight does not allow an unconfigured origin.
- [ ] Unauthorized requests return 401 where authentication is missing or invalid.
- [ ] Authenticated users without permission receive 403 for admin-only behavior.
- [ ] Responses never include `hashed_password`.

## Operational Checks

- [ ] `scripts/smoke_test.ps1` passes with seeded local credentials.
- [ ] Backend logs contain request IDs and no credentials or JWT secrets.
- [ ] Assignment command exits successfully when no due work exists.
- [ ] `docker-compose down` stops services while preserving the PostgreSQL volume.
- [ ] `docker-compose down -v` is used only when intentionally deleting local database data.

Record any failed item with route, role, timestamp, browser, and relevant backend log request ID.

## QA Run 2026-06-05 - Live Docker/PostgreSQL MVP Flow

### Environment

- Date: 2026-06-05.
- Environment: local Docker Desktop with `docker-compose`.
- Services: PostgreSQL, backend, frontend.
- Backend URL: `http://localhost:8000`.
- Frontend URL: `http://localhost:8080`.
- PostgreSQL migration revision: `0010 (head)`.
- QA mode: live API workflow against Docker/PostgreSQL plus frontend HTTP route checks.
- Backend runtime override for this QA run: `SAME_TEAM_PRIORITY_WINDOW_HOURS=0`, so the scheduled assignment command could process a newly created availability immediately.
- Browser UI click-through: not completed by Codex because the in-app browser runtime failed twice with a local sandbox startup error. Frontend routes were still verified by HTTP.

### Docker And Setup Commands Used

```powershell
docker-compose config
docker-compose up -d db backend frontend
docker-compose exec -T backend alembic -c alembic.ini upgrade head
docker-compose exec -T backend alembic -c alembic.ini current
docker-compose exec -T -e SEED_ADMIN_ENABLED=true -e SEED_ADMIN_EMAIL=qa.admin.manual@example.com -e SEED_ADMIN_USERNAME=qa_admin_manual -e SEED_ADMIN_FIRST_NAME=QA -e SEED_ADMIN_LAST_NAME=Admin -e SEED_ADMIN_PASSWORD="<local disposable password>" -e SEED_ADMIN_UPDATE_PASSWORD=true backend python -m app.commands.seed_admin
$env:SAME_TEAM_PRIORITY_WINDOW_HOURS="0"
docker-compose up -d --force-recreate backend
docker-compose exec -T backend python -m app.commands.assign_due_availabilities --limit 100
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke_test.ps1
docker-compose up -d --force-recreate backend
docker-compose exec -T backend alembic -c alembic.ini current
```

Passwords were supplied locally during command execution and were not recorded in this document.
After QA, the backend container was recreated without the `SAME_TEAM_PRIORITY_WINDOW_HOURS=0` shell override to restore normal Compose configuration.

### Disposable QA Users And Data

- Admin: `qa_admin_manual`.
- Employee: `qa_employee_20260605012932`.
- Second employee: `qa_employee2_20260605012932`.
- Parking owner: `qa_owner_20260605012932`.
- Team ID: `6`.
- Main availability ID: `3`.
- Initial reservation ID: `1`.
- Reassigned reservation ID: `2`.

### Passed Checks

- Admin username login returned a bearer token.
- Admin email login returned a bearer token.
- Swagger OAuth2 password-form token endpoint worked.
- Wrong password returned generic `401`.
- Unknown username returned generic `401`.
- Inactive user login returned `401`.
- `/auth/me` did not expose `hashed_password`.
- Missing token returned `401`.
- Non-admin access to admin route returned `403`.
- Admin created team, employee, second employee, parking owner, inactive user, and parking spots through the API.
- Employee and parking owner logins succeeded.
- Frontend nginx fallback returned HTTP `200` for `/`, `/login`, `/dashboard`, `/availabilities`, and `/admin`.
- Backend health returned HTTP `200`.
- Request ID header was returned.
- Security headers were returned.
- CORS preflight succeeded for `http://localhost:8080`.
- Disallowed CORS origin was rejected.
- Parking owner published an availability.
- Parking owner could see the availability in `my availabilities`.
- Employee could see the availability in available spots.
- Employee submitted an application.
- Duplicate application was blocked.
- Parking owner could not apply to their own availability.
- Employee could see the application in `my applications`.
- Employee could cancel a pending application.
- Assignment command completed with `processed=1 assigned=1 skipped=0 failed=0`.
- Availability status changed to `assigned`.
- Application status changed to `selected`.
- Employee could see assigned reservation.
- Admin could see applications.
- Admin could see reservation history.
- Admin could see assignment audit logs.
- Admin report endpoints and CSV exports returned HTTP `200`.
- Employee reservation cancellation succeeded.
- Availability reopened after employee reservation cancellation.
- Reassignment after cancellation created a new active reservation for the second employee.
- Parking owner reservation cancellation succeeded for an owned availability.
- Admin manual override assignment required a reason.
- Admin manual override assignment succeeded with a reason.
- Admin reservation cancellation required a reason.
- Admin reservation cancellation succeeded with a reason.
- `scripts/smoke_test.ps1` passed with disposable admin credentials.
- Backend logs did not contain the disposable QA passwords used in this run.

### Failed Or Not Fully Verified Checks

- Failed: admin replacement override could not be verified through the public workflow.
- Not fully verified by Codex: browser UI click-through, visual layout, responsive behavior, and screenshots. The browser automation runtime was unavailable in this session.
- Not fully verified by Codex: creating team, users, and parking spots through the admin UI. The same setup was verified through live admin API calls.

### Defect Note: Replacement Override Not Reachable

- Expected behavior: an admin can perform a replacement override from an assigned availability by selecting a pending replacement application.
- Actual behavior: after assignment, non-selected pending applications are rejected, and public application creation rejects assigned availabilities because they are no longer open. That leaves no public UI/API path to create or retain a pending replacement application for `/admin/parking-availabilities/{availability_id}/replace-reservation`.
- Steps to reproduce:
  1. Create a parking owner, employee, parking spot, and availability.
  2. Submit an employee application.
  3. Assign the availability.
  4. Try to create another application for the assigned availability, or try to replace with an existing non-pending application.
  5. Replacement cannot be completed through the public workflow because the replacement endpoint requires a pending application.
- Affected role: admin.
- Affected endpoint/page: `POST /admin/parking-availabilities/{availability_id}/replace-reservation`, Admin Overrides UI.
- Suggested fix area: define the intended replacement-candidate workflow. Options include allowing admin-created replacement candidates, retaining non-selected candidates as pending for override workflows, or explicitly allowing replacement from a rejected candidate with an admin reason.

### Defect Resolution Verification: Replacement Override Reachability

- Date: 2026-06-05.
- Selected design: Option B. Admin replacement override now accepts exactly one of `application_id` or `applicant_id`.
- Existing `application_id` behavior remains pending-application based.
- New `applicant_id` behavior is admin-only. It creates an internal replacement application when none exists, or reactivates an existing rejected/cancelled application for the same availability/applicant, then performs the replacement.
- Normal employee rules remain unchanged: employees still cannot apply to assigned availabilities.
- Live Docker/PostgreSQL smoke result: passed. A disposable admin, owner, current employee, replacement employee, team, spot, availability, application, assignment, applicant-ID replacement, and replacement audit log were created through the API.
- Verified replacement audit fields: `action = replacement`, override reason, admin actor, previous user/application, selected user/application, requested applicant, and candidate action.
- Frontend nginx/Vue Router fallback was verified on temporary port `18080` for `/`, `/login`, `/dashboard`, `/availabilities`, and `/admin`.
- Limitation in this environment: Compose frontend could not bind host port `8080` because it was already allocated outside the visible Compose project, so the configured `http://localhost:8080` frontend smoke was verified through the same built image on `http://localhost:18080`.

### Final Release-Candidate Status

Status: not approved for full release-candidate sign-off yet.

Reason: the replacement override defect is fixed and smoke-verified, but browser UI click-through, screenshots, responsive visual verification, and the full manual checklist still need a human QA pass.

## QA Run 2026-06-19 - Applicant ID Replacement RC QA

### Environment

- Date: 2026-06-19.
- Environment: local Docker Desktop with standalone `docker-compose`.
- Backend URL: `http://localhost:8000`.
- Frontend URL: `http://localhost:8080`.
- Docker services: PostgreSQL, backend, frontend.
- PostgreSQL migration revision: `0010 (head)`.
- Backend runtime override for this QA run: `SAME_TEAM_PRIORITY_WINDOW_HOURS=0`, so the assignment command could assign the newly created future availability immediately after the application was submitted.
- Browser UI click-through: not completed by Codex because the in-app browser runtime failed twice before page interaction with a local sandbox startup error.

### Docker And Verification Commands

```powershell
docker-compose config --quiet
docker-compose build backend frontend
$env:SAME_TEAM_PRIORITY_WINDOW_HOURS="0"
docker-compose up -d db backend frontend
docker-compose exec -T backend alembic -c alembic.ini upgrade head
docker-compose exec -T backend alembic -c alembic.ini current
docker-compose exec -T backend python -m app.commands.assign_due_availabilities --limit 100
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke_test.ps1
docker-compose down
```

### Disposable QA Users And Data

- Admin: `rcqa_admin_1780644123674`.
- Parking owner: `rcqa_owner_1780644481335`.
- Employee A: `rcqa_employee_a_1780644481335`.
- Employee B: `rcqa_employee_b_1780644481335`.
- Team ID: `10`.
- Parking spot ID: `10`.
- Replacement availability ID: `16`.
- Replacement reservation ID: `11`.
- Replacement audit log ID: `17`.

Passwords were generated for disposable local users during command execution and were not recorded. A temporary local credential file used by Codex was deleted after QA.

### Applicant ID Replacement Result

- Result: passed at API/backend-contract level.
- Assignment command result: `processed=1 assigned=1 skipped=0 failed=0`.
- Employee A submitted the original application and received the initial active reservation.
- Admin replacement override was submitted with `applicant_id` for Employee B and mandatory reason `RC QA applicant ID replacement`.
- The active reservation was updated in place and became assigned to Employee B.
- Employee A no longer had the active reservation after replacement.
- Employee B could see the active replacement reservation.
- Normal employee application to the assigned availability remained blocked with `409` and `Parking availability is not open`.
- Replacement audit log contained `action = replacement`, reason, previous user, selected user, requested applicant, and admin override ranking policy.

### Broader Regression Result

- Authentication: passed for username login, email login, wrong-password `401`, unknown-user `401`, inactive-user `401`, invalid-token `401`, and `/auth/me` response safety.
- Authorization: passed for non-admin `403` on admin route.
- Admin setup: passed for team, users, inactive user, and parking spot creation through API.
- Owner: passed for publishing availability, listing own availabilities, cancelling availability, owner assignment, owner reservation cancellation, and reassignment after cancellation.
- Employee: passed for viewing open availability, applying, duplicate application blocking, owner self-application blocking, viewing own applications, cancelling own pending application, viewing own reservation, and replacement visibility.
- Admin: passed for applications list, reservations list, reservation history, assignment audit logs, reports, CSV exports, manual override assignment, replacement override by Applicant ID, and admin cancellation through `/admin/parking-reservations/{reservation_id}/cancel`.
- Frontend routing: nginx/Vue Router fallback returned HTTP `200` with Vue root content for `/`, `/login`, `/dashboard`, `/availabilities`, and `/admin`.
- Backend security smoke: health, request ID, security headers, allowed CORS preflight, and disallowed CORS origin behavior passed.
- `scripts/smoke_test.ps1`: passed after rerunning with Docker access so the Alembic revision checks could execute.

### Failed Or Not Fully Verified Checks

- Not fully verified: Admin Overrides UI Applicant ID replacement browser click-through. The backend/API flow and frontend route delivery passed, but the in-app browser runtime could not start in this environment.
- Not fully verified: screenshots, responsive visual layout, and human browser inspection.
- Resolved on 2026-06-20: frontend dependency audit blocker.
  - `form-data` was updated from `4.0.5` to `4.0.6` through the existing `axios` dependency range.
  - `undici` was updated from `7.27.1` to `7.28.0` through the existing `jsdom` dependency range.
  - No package overrides, forced major upgrades, or application code changes were required.
  - `npm.cmd audit`, `npm.cmd audit --omit=dev`, `npm.cmd audit --omit=optional`, and `npm.cmd audit --json` now report `0` vulnerabilities.

### Release-Candidate Status

Status: not approved for full release-candidate sign-off.

Reason: the Applicant ID replacement workflow passed API-backed QA and the frontend dependency audit blocker is resolved, but browser UI click-through/visual QA is still blocked by the local browser runtime.

## QA Run 2026-06-20 - Browser Admin Overrides Applicant ID Replacement

### Environment

- Date: 2026-06-20.
- Environment: local Docker Desktop with standalone `docker-compose`.
- Browser: Codex in-app browser runtime against the real local frontend. The runtime did not expose a browser user-agent string to page evaluation.
- Backend URL: `http://localhost:8000`.
- Frontend URL: `http://localhost:8080`.
- Docker services: PostgreSQL, backend, frontend.
- PostgreSQL migration revision: `0010 (head)`.
- Runtime override: `SAME_TEAM_PRIORITY_WINDOW_HOURS=0`, so the assignment command could assign the newly created future availability immediately after Employee A applied.

### Commands Used

```powershell
docker-compose config
$env:SEED_ADMIN_ENABLED="false"
$env:SAME_TEAM_PRIORITY_WINDOW_HOURS="0"
docker-compose up -d db backend frontend
docker-compose exec -T backend alembic -c alembic.ini upgrade head
docker-compose exec -T backend alembic -c alembic.ini current
docker-compose exec -T backend python -m app.commands.assign_due_availabilities --limit 100
docker-compose build frontend
docker-compose up -d frontend
docker-compose down
```

### Disposable QA Users And Data

- Admin: `browserqa_admin_1781956103179`.
- Parking owner: `browserqa_owner_1781956103179`.
- Employee A: `browserqa_employee_a_1781956103179`.
- Employee B: `browserqa_employee_b_1781956103179`.
- Team ID: `42`.
- Parking owner user ID: `56`.
- Employee A user ID: `57`.
- Employee B user ID: `58`.
- Parking spot ID: `42`.
- Availability ID: `45`.
- Employee A application ID: `47`.
- Replacement application ID: `48`.
- Reservation ID: `42`.

Passwords were generated only for disposable local QA accounts and were not committed or documented.

### Browser Flow Result

- Admin logged in through the frontend login page.
- Admin created the team, parking owner, Employee A, Employee B, and parking spot through the admin UI.
- Admin forms showed success feedback after each create action.
- Parking owner logged in through the UI and published a valid future availability for parking spot `#42`.
- Owner My availabilities page showed the published availability.
- Employee A logged in through the UI, opened available spots, applied for the availability, and saw the pending application in My applications.
- Assignment command result: `processed=1 assigned=1 skipped=0 failed=0`.
- Employee A My reservations showed reservation `#42` as `Active`.
- Employee A My applications showed application `#47` as `Selected`.

### Applicant ID Replacement UI Result

- Admin opened Admin Overrides in the browser.
- Replacement form accepted availability ID `45` plus Applicant ID `58` without requiring an application ID.
- Replacement succeeded through the UI and returned reservation summary:
  - reservation `#42`,
  - availability `#45`,
  - application `#48`,
  - parking spot `#42`,
  - reserved for user `#58`,
  - status `Active`.
- Success feedback was visible.
- No stale validation error was visible on the successful replacement state.
- The actual non-blank audit reason recorded for the successful replacement was `Missing selector validation`; this occurred during validation sequencing when Applicant ID `58` remained populated. The result still verifies the required Applicant ID path with no `application_id`.

### Validation And Error UX

- Blank reason was blocked with client-side validation: `Reason is required.`
- Missing application/applicant selector was blocked with client-side validation: `Enter either an application ID or an applicant ID.`
- Providing both application ID and applicant ID was blocked with the same clear selector validation message.
- Invalid applicant ID produced a clear error: `The selected applicant could not be found.`
- Reusing the current reserved user as replacement was blocked with: `The selected applicant already has the active reservation.`
- Repeated same-applicant submission did not create a duplicate replacement; the reservation remained assigned to Employee B.
- The replacement submit button is disabled while its loading prop is active through the shared `BaseButton` behavior.

### Post-Replacement Browser Verification

- Employee A no longer showed the active reservation.
- Employee B saw the active replacement reservation.
- Admin reservation history showed reservation `#42` reserved for user `#58` with `Active` and `Current Active` status.
- Admin applications showed replacement application `#48` for applicant `#58` as `Selected`.
- Admin audit logs showed:
  - `action = replacement`,
  - `assignment_method = admin_override`,
  - non-blank override reason,
  - acting admin user ID `55`,
  - previous application `#47`,
  - previous user `#57`,
  - selected application `#48`,
  - selected user `#58`,
  - rejected application list containing `47`.
- Admin reports remained accessible.

### Visual And Responsive QA

- Desktop checks at `1280x800` passed for Admin Overrides and Admin Audit Logs:
  - no page-level horizontal overflow,
  - no offscreen visible controls,
  - form fields and buttons were reachable,
  - audit table remained inside its table scroll wrapper.
- Initial mobile check at `390x844` found a responsive defect:
  - the mobile navigation used five `max-content` columns,
  - the application shell expanded to roughly `821px`,
  - Admin Overrides controls were offscreen.
- Fix applied:
  - at `max-width: 640px`, `.app-shell__nav` now uses `repeat(2, minmax(0, 1fr))` and disables horizontal nav overflow.
- Final mobile checks at `390x844` passed for Admin Overrides and Admin Audit Logs:
  - no page-level horizontal overflow,
  - no offscreen visible controls,
  - no tiny unusable fields,
  - wide audit table remained usable inside `.data-table-wrap` horizontal scrolling.

### Browser Regression

- Login/logout passed across admin, employee, and parking-owner roles.
- Role-based navigation passed:
  - admin navigation exposed admin modules,
  - employee and owner workflow pages remained accessible for their roles.
- Employee pages passed:
  - available spots,
  - my applications,
  - my reservations.
- Owner page passed:
  - my availabilities.
- Admin pages passed:
  - applications,
  - reservations,
  - audit logs,
  - reports,
  - overrides,
  - admin dashboard.

### Automated Verification

- Backend tests:
  - Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m pytest`.
  - Result: `595` passed, `1` existing Starlette/httpx deprecation warning.
- Backend compile check:
  - Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m compileall app tests`.
  - Result: passed.
- Alembic:
  - `heads`: `0010 (head)`.
  - `history`: migrations `0001` through `0010` listed.
  - Docker `current`: `0010 (head)`.
- Frontend tests:
  - Command: `npm.cmd test`.
  - Result: `43` passed across `17` files.
- Frontend production build:
  - Command: `npm.cmd run build`.
  - Result: passed.
- Frontend Docker build after responsive fix:
  - Command: `docker-compose build frontend`.
  - Result: passed.
- Dependency audit:
  - `npm.cmd audit`: `0` vulnerabilities.
  - `npm.cmd audit --omit=dev`: `0` vulnerabilities.
  - `npm.cmd audit --omit=optional`: `0` vulnerabilities.

### Release-Candidate Status

Status: APPROVED.

Reason: the Applicant ID replacement workflow passed through the actual browser UI, critical MVP browser regression flows passed, the dependency audit blocker remains resolved, the responsive UI defect found during QA was fixed and reverified, and no unresolved release blockers remain.
