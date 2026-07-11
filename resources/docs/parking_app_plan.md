# Company Parking Management Application Plan

## 1. Project Overview

The goal is to build an internal company parking management application where employees with permanently assigned parking spots can temporarily release their spots for a specific day, multiple days, or a specific time interval. Other employees can apply to use those available spots. The system then selects or confirms one employee for each availability period and prevents further applications once the spot is assigned.

The application should be practical for a company environment, transparent in how assignments are made, and simple enough to operate without constant administrative work. The recommended approach is an automatic assignment model with configurable priority and fairness rules, plus admin override for exceptional cases.

### Primary Users

- Employees who need temporary parking.
- Parking spot owners who have permanently assigned spots and can publish temporary availability.
- Administrators who manage employees, teams, parking spots, and exceptional assignment changes.

### Target Stack

- Backend: Python FastAPI.
- Database: PostgreSQL.
- ORM: SQLAlchemy.
- Migrations: Alembic.
- Validation: Pydantic.
- Frontend: Vue.js.
- Authentication: JWT-based login flow.
- Deployment: Dockerized backend, frontend, and PostgreSQL using Docker Compose.

### High-Level System Behavior

1. Admins create employees, teams, and parking spots.
2. Some employees are assigned as default owners of parking spots.
3. A parking spot owner publishes availability for their spot.
4. Other employees apply for the published availability.
5. The system applies priority and fairness rules.
6. One applicant is assigned the spot for the published period.
7. The availability is closed and no more applications are accepted.
8. Admins can audit and override assignments if needed.

## 2. Business Requirements

### 2.1 Employees and Teams

Employees represent company users who can log in and interact with the system.

Each employee should have:

- Unique ID.
- Email address.
- Full name.
- Password hash or external identity reference.
- Team membership.
- Role assignment.
- Active/inactive status.
- Created and updated timestamps.

Teams are used for priority logic. Employees from the same team as a parking spot owner receive priority during a configurable initial priority window.

Team records should include:

- Unique ID.
- Team name.
- Optional description.
- Active/inactive status.
- Created and updated timestamps.

### 2.2 Parking Spots

Parking spots represent physical company parking places.

Each parking spot should have:

- Unique ID.
- Spot code or label, such as `A-12`, `Garage-03`, or `P1-042`.
- Optional location details, such as building, floor, zone, or notes.
- Active/inactive status.
- Created and updated timestamps.

Some parking spots have permanently assigned owners. A spot should have at most one active default owner at a time. The ownership relationship should be modeled separately from the parking spot record so ownership history can be preserved.

### 2.3 Parking Spot Ownership

Ownership defines which employee normally owns a parking spot.

Ownership records should include:

- Unique ID.
- Parking spot ID.
- Owner employee ID.
- Start date.
- Optional end date.
- Active flag.
- Created and updated timestamps.

Rules:

- Only the current active owner can publish availability for a spot.
- A spot should not have multiple active owners at the same time.
- Historical ownership should remain available for audit purposes.

### 2.4 Publishing Availability

A parking spot owner can publish their assigned parking spot as available for:

- One specific day.
- Multiple consecutive days.
- A specific date/time interval.

Availability records should include:

- Unique ID.
- Parking spot ID.
- Owner employee ID.
- Start date/time.
- End date/time.
- Published date/time.
- Priority window end date/time.
- Status.
- Optional note.
- Created and updated timestamps.

Recommended statuses:

- `draft`: Optional future state if the UI supports saving before publishing.
- `open`: Published and accepting applications.
- `reserved`: An employee has been selected and assigned.
- `cancelled`: Owner or admin cancelled before assignment.
- `expired`: Availability passed without a valid assignment.

Rules:

- Start date/time must be before end date/time.
- The owner must be the active assigned owner of the parking spot.
- The same parking spot cannot have overlapping active availabilities.
- The owner can cancel an availability only while it is not reserved.
- Once reserved, the availability no longer accepts applications.
- Availability times should be stored in UTC and displayed in the user's local timezone.

### 2.5 Applying for an Available Parking Spot

Employees can apply for an open availability.

Application records should include:

- Unique ID.
- Availability ID.
- Applicant employee ID.
- Status.
- Application timestamp.
- Optional cancellation timestamp.
- Created and updated timestamps.

Recommended statuses:

- `pending`: Application is active and waiting for assignment.
- `cancelled`: Applicant cancelled before assignment.
- `selected`: Applicant was selected for the reservation.
- `rejected`: Application was not selected after another employee was assigned.

Rules:

- The parking spot owner cannot apply for their own availability.
- An employee cannot apply more than once for the same availability.
- Inactive employees cannot apply.
- Employees can cancel their own pending applications before assignment.
- Applications should remain in history after cancellation or rejection.
- The system should keep application timestamps for fairness, auditing, and tie-breaking.

### 2.6 Reservation and Assignment

A reservation or assignment represents the final decision that a specific employee gets a parking spot for a published availability period.

Reservation records should include:

- Unique ID.
- Availability ID.
- Parking spot ID.
- Assigned employee ID.
- Owner employee ID.
- Start date/time.
- End date/time.
- Assignment method.
- Assignment timestamp.
- Assigned by user ID, if manual or admin override.
- Optional note.
- Created and updated timestamps.

Recommended assignment methods:

- `automatic`: System selected the employee using configured priority and fairness rules.
- `owner_manual`: Owner selected the employee manually, if this mode is enabled.
- `admin_override`: Admin assigned or changed the reservation.

Rules:

- Each availability can have at most one active reservation.
- Once a reservation is created, the availability status becomes `reserved`.
- All non-selected pending applications become `rejected`.
- No further applications are accepted after reservation.
- Admins can override reservations, but overrides must be auditable.

## 3. Recommended Fairness and Priority Model

### 3.1 Recommendation Summary

Use automatic assignment after a configurable priority window, with a fair rotation score and application timestamp as the tie-breaker.

Recommended default:

- Priority window: 4 business hours after publication.
- Priority group: employees from the same team as the parking spot owner.
- Assignment timing: automatic when the priority window ends.
- Selection method: lowest recent win count first, then earliest application timestamp.
- Cooldown rule: configurable limit on recent wins, such as no more than 2 wins per employee in a rolling 14-day period unless there are no other eligible applicants.
- Admin override: allowed and audited.
- Owner manual selection: not recommended as the default because it can create bias and delays.

This model is transparent, easy to explain, easy to audit, and fair enough for an internal company tool.

### 3.2 Why Not Pure First Come First Served

Pure first come first served is simple, but it rewards employees who check the app constantly and can be unfair to employees in meetings, different shifts, or time zones. It is acceptable as a tie-breaker, but it should not be the only rule.

### 3.3 Why Not Weighted Random as the Default

Weighted random selection can be fair statistically over time, but it is harder for users to understand. Employees may perceive random assignment as arbitrary, even when the weighting is reasonable. It also makes support and audit conversations more difficult.

Weighted random can be considered later for high-demand environments, but it should not be the initial default.

### 3.4 Why Not Owner Manual Approval as the Default

Manual owner approval gives the spot owner control, but it has several problems:

- It creates delays.
- It can produce favoritism or perceived favoritism.
- It requires the owner to monitor applications.
- It creates inconsistent outcomes across teams.

Owner manual approval can be offered as an optional configuration, but the most practical default is automatic assignment.

### 3.5 Recommended Selection Algorithm

When a parking availability is published:

1. Set `priority_window_end_at = published_at + configured_priority_window`.
2. Keep the availability open for applications during the priority window.
3. Allow all employees to submit applications immediately, but mark whether each applicant is in the same team as the owner.
4. When the priority window expires, select the winner.
5. If at least one same-team applicant exists, choose only from same-team applicants.
6. If no same-team applicant exists, choose from all active applicants.
7. Rank eligible applicants by:
   - Fewest parking wins in the configured recent period.
   - Earliest application timestamp.
   - Stable deterministic tie-breaker, such as lowest application ID.
8. Create a reservation for the winning applicant.
9. Mark the selected application as `selected`.
10. Mark other pending applications as `rejected`.
11. Mark the availability as `reserved`.

This allows employees outside the priority team to apply immediately, but they only become eligible if there are no same-team applicants during the priority window.

### 3.6 Handling Late Applications

Once the priority window has expired, the system should assign the spot immediately if there are pending applications. After assignment, late applications are not accepted.

If there are no applications at priority window expiration:

- Keep the availability open.
- The first eligible applicant after the window can be assigned automatically.
- If multiple applications arrive before processing, use the same fairness ranking.

This prevents empty availabilities from sitting idle while still preserving fairness when there is demand.

### 3.7 Cooldown and Win Limits

To avoid the same employee repeatedly winning parking spots, configure a rolling win limit.

Recommended initial configuration:

- Rolling period: 14 days.
- Soft limit: 2 wins.
- If an applicant has reached the soft limit and other eligible applicants have not, prefer the other applicants.
- If all eligible applicants have reached the soft limit, ignore the limit and use the normal ranking.

This should be implemented as a soft fairness rule, not a hard block. Hard blocks can waste parking capacity when only frequent applicants are available.

### 3.8 Priority Window Duration

Recommended default:

- 4 business hours for normal availability.

Alternative configuration:

- 2 hours for same-day urgent availability.
- 8 business hours for highly constrained parking environments.
- No priority window for spots explicitly marked company-wide.

The system should store this as configuration so the company can tune behavior without code changes.

### 3.9 Auditability

Every assignment should record:

- Assignment method.
- Candidate pool used for selection.
- Winning employee.
- Fairness ranking inputs, such as recent win count and application timestamp.
- User who performed the assignment, if manual.
- Timestamp of assignment.

At minimum, the system should make the final decision explainable to admins.

## 4. User Roles and Permissions

### 4.1 Employee

Employees can:

- Log in.
- View open parking availabilities.
- View availability details.
- Apply for open availabilities.
- Cancel their own pending applications.
- View their own applications and results.
- View their active and past reservations.

Employees cannot:

- Apply for their own parking spot availability.
- Create parking spots.
- Manage other employees.
- Override assignments.

### 4.2 Parking Spot Owner

A parking spot owner is an employee who currently owns one or more assigned parking spots. This can be treated as a capability derived from ownership, not necessarily a separate global role.

Parking spot owners can:

- Publish availability for their own assigned spots.
- View applications for their published availabilities.
- Cancel their published availability before assignment.
- View reservation history for their spots.

Parking spot owners cannot:

- Publish availability for spots they do not own.
- Cancel availability after reservation, unless admin rules allow it.
- Assign a winner manually by default.

### 4.3 Admin

Admins can:

- Manage employees.
- Manage teams.
- Manage parking spots.
- Manage parking spot ownership.
- View all availabilities, applications, and reservations.
- Cancel availabilities.
- Override assignments.
- Reassign a reservation if needed.
- Deactivate users, teams, and parking spots.
- Review audit logs.

### 4.4 Optional Role Model

Initial roles:

- `employee`
- `admin`

Spot owner permissions should be derived from active parking spot ownership. If future requirements need dedicated owner permissions, a `spot_owner` role can be added, but it is not necessary for the first version.

## 5. Main User Flows

### 5.1 Login Flow

1. User opens the frontend login page.
2. User enters email and password.
3. Frontend sends credentials to `POST /auth/login`.
4. Backend verifies credentials.
5. Backend returns a JWT access token and, optionally, a refresh token.
6. Frontend stores authentication state.
7. Frontend loads the user profile from `GET /auth/me`.
8. User is redirected to the dashboard.

### 5.2 Publish Parking Spot Availability

1. Parking spot owner opens "My Parking Spot" or "Publish Availability".
2. System loads the owner's active parking spots.
3. Owner selects a spot.
4. Owner chooses start date/time and end date/time.
5. Owner optionally adds a note.
6. Frontend validates basic date/time rules.
7. Backend validates ownership and overlapping availability.
8. Backend creates availability with status `open`.
9. Backend calculates `priority_window_end_at`.
10. Availability appears in the available parking list.

### 5.3 Apply for a Parking Spot

1. Employee opens available parking list.
2. Employee filters by date, location, team priority, or status.
3. Employee opens an availability detail page or row action.
4. Employee clicks "Apply".
5. Backend validates that:
   - Availability is open.
   - Employee is not the owner.
   - Employee has not already applied.
   - Employee is active.
6. Backend creates a pending application.
7. UI updates application state.

### 5.4 Cancel My Application

1. Employee opens "My Applications".
2. Employee selects a pending application.
3. Employee clicks cancel.
4. Backend confirms the availability is not reserved for that employee.
5. Backend marks the application as `cancelled`.
6. UI updates the application list.

### 5.5 Automatic Assignment

1. Availability reaches priority window expiration.
2. Background worker or scheduled job finds open availabilities ready for assignment.
3. System loads active pending applications.
4. System applies priority and fairness ranking.
5. System creates a reservation.
6. System updates availability and application statuses.
7. System emits notifications or makes status visible in the UI.

### 5.6 Admin Override

1. Admin opens availability or reservation details.
2. Admin reviews applications and current reservation.
3. Admin selects an override action.
4. Admin must provide an override reason.
5. Backend records the change in reservation and audit history.
6. Affected users can see updated status.

## 6. Backend Architecture

### 6.1 Recommended Structure

Use a clean service-repository structure:

```text
backend/
  alembic/
  app/
    main.py
    core/
      config.py
      security.py
      permissions.py
    db/
      base.py
      session.py
    models/
      user.py
      team.py
      role.py
      parking_spot.py
      parking_ownership.py
      parking_availability.py
      parking_application.py
      parking_reservation.py
      audit_log.py
    schemas/
      auth.py
      user.py
      team.py
      parking_spot.py
      parking_availability.py
      parking_application.py
      parking_reservation.py
    repositories/
      user_repository.py
      team_repository.py
      parking_spot_repository.py
      parking_availability_repository.py
      parking_application_repository.py
      parking_reservation_repository.py
    services/
      auth_service.py
      user_service.py
      parking_availability_service.py
      parking_application_service.py
      parking_assignment_service.py
      admin_service.py
    routers/
      auth.py
      users.py
      teams.py
      parking_spots.py
      parking_availabilities.py
      parking_applications.py
      parking_reservations.py
      admin.py
    workers/
      assignment_worker.py
    tests/
```

### 6.2 Layer Responsibilities

Models:

- Define SQLAlchemy ORM entities.
- Contain database relationships and constraints.
- Avoid business process logic.

Schemas:

- Define Pydantic request and response models.
- Validate API payload shape.
- Keep API contracts independent from ORM objects.

Repositories:

- Encapsulate database queries.
- Provide methods such as `get_by_id`, `list_open`, `create`, `update_status`.
- Avoid business decision logic.

Services:

- Implement business rules.
- Handle transactions.
- Coordinate multiple repositories.
- Enforce ownership, priority, assignment, and cancellation rules.

Routers:

- Define FastAPI endpoints.
- Handle dependency injection.
- Call services.
- Return response schemas.

Workers:

- Run scheduled assignment checks.
- Process availabilities whose priority window has expired.
- Can start as a simple periodic process and later move to Celery, RQ, or APScheduler.

### 6.3 Transaction Boundaries

Operations that modify multiple records must run in a database transaction:

- Applying for an availability.
- Cancelling an availability.
- Assigning a reservation.
- Admin override.

The assignment process should lock the availability row during selection to prevent duplicate reservations when multiple workers or requests run concurrently.

Recommended database techniques:

- Use unique constraints for duplicate prevention.
- Use transaction-level row locks for assignment.
- Use `SELECT ... FOR UPDATE` through SQLAlchemy for reservation creation.

### 6.4 Authentication Flow

Use a simple JWT-based flow for the first version.

Recommended behavior:

1. User logs in with email and password.
2. Backend verifies password using a secure hash such as bcrypt.
3. Backend returns:
   - Short-lived access token, for example 15 to 30 minutes.
   - Refresh token, for example 7 days, ideally stored in an HttpOnly cookie.
4. Frontend sends access token in the `Authorization: Bearer <token>` header.
5. Backend validates the token for protected endpoints.
6. Frontend refreshes the access token when it expires.
7. Logout clears local auth state and invalidates refresh token if refresh tokens are stored server-side.

JWT claims should include:

- `sub`: user ID.
- `email`: user email.
- `role`: user role.
- `exp`: expiration timestamp.
- `iat`: issued-at timestamp.

Future improvement:

- Integrate with company SSO, such as Azure AD / Entra ID, using OIDC.

### 6.5 Authorization

Authorization should be enforced in services, not only in frontend UI.

Examples:

- `require_admin(user)` for admin endpoints.
- `require_active_user(user)` for application actions.
- `require_spot_owner(user, parking_spot_id)` for publishing availability.
- `can_cancel_availability(user, availability)` for owner/admin cancellation.

### 6.6 Background Assignment

The first version can use a scheduled worker that runs every minute.

Worker responsibilities:

- Find open availabilities where `priority_window_end_at <= now`.
- Find open availabilities past start time with no applications and mark them `expired`.
- Run assignment service for eligible availabilities.
- Log assignment decisions.

Possible implementation options:

- Simple FastAPI startup background task for development.
- APScheduler inside backend container.
- Celery with Redis for a more scalable later version.

Recommended first implementation:

- Use APScheduler or a dedicated backend worker process started from the same backend image.
- Keep assignment logic in `parking_assignment_service.py` so it is reusable from API and worker contexts.

## 7. Frontend Architecture

### 7.1 Recommended Structure

Use Vue 3 with Vite, Vue Router, Pinia, and Axios or Fetch-based API services.

```text
frontend/
  src/
    main.ts
    App.vue
    router/
      index.ts
    stores/
      authStore.ts
      parkingStore.ts
    services/
      apiClient.ts
      authApi.ts
      availabilityApi.ts
      applicationApi.ts
      adminApi.ts
    layouts/
      AppLayout.vue
      AuthLayout.vue
      AdminLayout.vue
    pages/
      LoginPage.vue
      DashboardPage.vue
      AvailableSpotsPage.vue
      AvailabilityDetailPage.vue
      PublishAvailabilityPage.vue
      MyApplicationsPage.vue
      MyReservationsPage.vue
      AdminEmployeesPage.vue
      AdminTeamsPage.vue
      AdminParkingSpotsPage.vue
    components/
      navigation/
        AppSidebar.vue
        TopBar.vue
      availability/
        AvailabilityCard.vue
        AvailabilityTable.vue
        PublishAvailabilityForm.vue
        ApplicationList.vue
      admin/
        EmployeeForm.vue
        TeamForm.vue
        ParkingSpotForm.vue
      common/
        BaseButton.vue
        BaseInput.vue
        BaseSelect.vue
        BaseModal.vue
        StatusBadge.vue
        EmptyState.vue
        LoadingState.vue
```

### 7.2 Main Pages

Login page:

- Email field.
- Password field.
- Login button.
- Error message area.

Dashboard:

- Summary of open availabilities.
- My pending applications.
- My assigned reservations.
- My owned spot availability status, if applicable.
- Admin shortcuts for admin users.

Available parking spots:

- Table or card list of open availabilities.
- Filters by date, location, team priority, and status.
- Apply action.
- Status badges for priority window and availability state.

Publish availability:

- Spot selector for owned spots.
- Start date/time input.
- End date/time input.
- Optional note.
- Submit and cancel actions.

My applications:

- Pending applications.
- Selected reservations.
- Rejected applications.
- Cancelled applications.
- Cancel button for pending applications.

Admin employees:

- Employee list.
- Create/edit/deactivate employees.
- Assign team and role.

Admin teams:

- Team list.
- Create/edit/deactivate teams.

Admin parking spots:

- Parking spot list.
- Create/edit/deactivate spots.
- Assign owners.
- View ownership history.

### 7.3 Frontend API Services

Keep API calls outside page components.

Example service modules:

- `authApi.ts`: login, refresh, logout, current user.
- `availabilityApi.ts`: list, detail, create, cancel.
- `applicationApi.ts`: apply, cancel, list mine.
- `adminApi.ts`: employee, team, parking spot management.

The API client should:

- Attach JWT access token.
- Handle 401 responses.
- Refresh tokens if refresh flow is enabled.
- Normalize backend errors into UI-friendly messages.

## 8. UI Design System

### 8.1 Visual Direction

The UI should be clean, professional, and suitable for an internal company application. The design should primarily use blue and white, with restrained supporting colors for statuses and feedback.

The application should feel like an operational tool:

- Clear navigation.
- Dense but readable information.
- Consistent forms and tables.
- Minimal decorative elements.
- Fast scanning of availability and application statuses.

### 8.2 Color Palette

Recommended colors:

- Primary blue: `#2563EB`
- Dark blue: `#1E3A8A`
- Light blue background: `#EFF6FF`
- Blue hover: `#DBEAFE`
- White background: `#FFFFFF`
- Page background: `#F8FAFC`
- Border gray: `#E2E8F0`
- Text primary: `#0F172A`
- Text secondary: `#64748B`
- Disabled gray: `#CBD5E1`
- Success green: `#16A34A`
- Warning yellow/orange: `#F59E0B`
- Error red: `#DC2626`

### 8.3 Typography

Recommended typography:

- Font family: system UI stack, such as Inter if included, otherwise `system-ui`.
- Page title: 24px to 30px, semibold.
- Section title: 18px to 20px, semibold.
- Body text: 14px to 16px.
- Table text: 13px to 14px.
- Badge text: 12px to 13px.

### 8.4 Components

Buttons:

- Primary button: blue background, white text.
- Secondary button: white background, blue or gray text, gray border.
- Danger button: red background or red text depending on severity.
- Disabled state: muted gray with no hover effect.

Cards:

- White or light blue background.
- 1px gray border.
- 6px to 8px border radius.
- Subtle shadow only when needed.

Forms:

- Labels above fields.
- Clear validation messages.
- Required fields marked consistently.
- Date/time fields should use browser-friendly controls or a reliable date picker.

Tables:

- Sticky or clear header for long lists.
- Status badges.
- Row actions aligned consistently.
- Empty state when no data exists.

Status badges:

- `open`: blue.
- `priority`: light blue or dark blue.
- `pending`: yellow/orange.
- `reserved`: green.
- `cancelled`: gray or red depending on context.
- `rejected`: gray.
- `expired`: gray.

## 9. Database Schema Proposal

### 9.1 Tables

#### teams

| Column | Type | Notes |
| --- | --- | --- |
| id | UUID or BIGSERIAL | Primary key |
| name | VARCHAR(120) | Unique, required |
| description | TEXT | Optional |
| is_active | BOOLEAN | Default true |
| created_at | TIMESTAMPTZ | Required |
| updated_at | TIMESTAMPTZ | Required |

#### users

| Column | Type | Notes |
| --- | --- | --- |
| id | UUID or BIGSERIAL | Primary key |
| email | VARCHAR(255) | Unique, required |
| full_name | VARCHAR(160) | Required |
| password_hash | VARCHAR(255) | Required for local auth |
| team_id | FK teams.id | Nullable only if allowed by business |
| role | VARCHAR(40) | `employee` or `admin` |
| is_active | BOOLEAN | Default true |
| created_at | TIMESTAMPTZ | Required |
| updated_at | TIMESTAMPTZ | Required |

#### parking_spots

| Column | Type | Notes |
| --- | --- | --- |
| id | UUID or BIGSERIAL | Primary key |
| code | VARCHAR(80) | Unique, required |
| location | VARCHAR(160) | Optional |
| description | TEXT | Optional |
| is_active | BOOLEAN | Default true |
| created_at | TIMESTAMPTZ | Required |
| updated_at | TIMESTAMPTZ | Required |

#### parking_spot_ownerships

| Column | Type | Notes |
| --- | --- | --- |
| id | UUID or BIGSERIAL | Primary key |
| parking_spot_id | FK parking_spots.id | Required |
| owner_user_id | FK users.id | Required |
| starts_at | TIMESTAMPTZ | Required |
| ends_at | TIMESTAMPTZ | Optional |
| is_active | BOOLEAN | Default true |
| created_at | TIMESTAMPTZ | Required |
| updated_at | TIMESTAMPTZ | Required |

Recommended constraints:

- Only one active ownership per parking spot.
- Optional uniqueness on active ownership by owner and parking spot.

#### parking_availabilities

| Column | Type | Notes |
| --- | --- | --- |
| id | UUID or BIGSERIAL | Primary key |
| parking_spot_id | FK parking_spots.id | Required |
| owner_user_id | FK users.id | Required |
| starts_at | TIMESTAMPTZ | Required |
| ends_at | TIMESTAMPTZ | Required |
| published_at | TIMESTAMPTZ | Required |
| priority_window_ends_at | TIMESTAMPTZ | Required |
| status | VARCHAR(40) | `open`, `reserved`, `cancelled`, `expired` |
| note | TEXT | Optional |
| cancelled_at | TIMESTAMPTZ | Optional |
| cancelled_by_user_id | FK users.id | Optional |
| created_at | TIMESTAMPTZ | Required |
| updated_at | TIMESTAMPTZ | Required |

Recommended constraints:

- `starts_at < ends_at`.
- Prevent overlapping open/reserved availabilities for the same parking spot.

For overlap prevention in PostgreSQL, consider an exclusion constraint using `tstzrange` and GiST indexes.

#### parking_applications

| Column | Type | Notes |
| --- | --- | --- |
| id | UUID or BIGSERIAL | Primary key |
| availability_id | FK parking_availabilities.id | Required |
| applicant_user_id | FK users.id | Required |
| status | VARCHAR(40) | `pending`, `cancelled`, `selected`, `rejected` |
| applied_at | TIMESTAMPTZ | Required |
| cancelled_at | TIMESTAMPTZ | Optional |
| created_at | TIMESTAMPTZ | Required |
| updated_at | TIMESTAMPTZ | Required |

Recommended constraints:

- Unique `(availability_id, applicant_user_id)` to prevent duplicate applications.
- Index on `(applicant_user_id, status)`.
- Index on `(availability_id, status, applied_at)`.

#### parking_reservations

| Column | Type | Notes |
| --- | --- | --- |
| id | UUID or BIGSERIAL | Primary key |
| availability_id | FK parking_availabilities.id | Required, unique |
| parking_spot_id | FK parking_spots.id | Required |
| assigned_user_id | FK users.id | Required |
| owner_user_id | FK users.id | Required |
| starts_at | TIMESTAMPTZ | Required |
| ends_at | TIMESTAMPTZ | Required |
| assignment_method | VARCHAR(40) | `automatic`, `owner_manual`, `admin_override` |
| assigned_by_user_id | FK users.id | Optional |
| assigned_at | TIMESTAMPTZ | Required |
| note | TEXT | Optional |
| created_at | TIMESTAMPTZ | Required |
| updated_at | TIMESTAMPTZ | Required |

Recommended constraints:

- Unique active reservation per availability.
- `starts_at < ends_at`.

#### audit_logs

| Column | Type | Notes |
| --- | --- | --- |
| id | UUID or BIGSERIAL | Primary key |
| actor_user_id | FK users.id | Nullable for system actions |
| action | VARCHAR(120) | Required |
| entity_type | VARCHAR(80) | Required |
| entity_id | VARCHAR(80) | Required |
| details | JSONB | Optional |
| created_at | TIMESTAMPTZ | Required |

Use audit logs for admin overrides, cancellations, assignment decisions, and ownership changes.

### 9.2 Optional Configuration Table

#### system_settings

| Column | Type | Notes |
| --- | --- | --- |
| key | VARCHAR(120) | Primary key |
| value | JSONB | Required |
| updated_at | TIMESTAMPTZ | Required |
| updated_by_user_id | FK users.id | Optional |

Example settings:

- `priority_window_hours`: `4`
- `urgent_priority_window_hours`: `2`
- `fairness_rolling_days`: `14`
- `fairness_soft_win_limit`: `2`

## 10. API Endpoint Proposal

### 10.1 Auth

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/auth/login` | Login with email and password |
| POST | `/auth/refresh` | Refresh access token |
| POST | `/auth/logout` | Logout and invalidate refresh token if supported |
| GET | `/auth/me` | Get current user profile |

### 10.2 Employees and Teams

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/users/me` | Get current employee profile |
| GET | `/admin/users` | List employees |
| POST | `/admin/users` | Create employee |
| GET | `/admin/users/{user_id}` | Get employee detail |
| PATCH | `/admin/users/{user_id}` | Update employee |
| DELETE | `/admin/users/{user_id}` | Deactivate employee |
| GET | `/admin/teams` | List teams |
| POST | `/admin/teams` | Create team |
| PATCH | `/admin/teams/{team_id}` | Update team |
| DELETE | `/admin/teams/{team_id}` | Deactivate team |

### 10.3 Parking Spots and Ownership

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/parking-spots` | List active parking spots visible to user |
| GET | `/parking-spots/my` | List spots owned by current user |
| GET | `/admin/parking-spots` | Admin list parking spots |
| POST | `/admin/parking-spots` | Create parking spot |
| PATCH | `/admin/parking-spots/{spot_id}` | Update parking spot |
| DELETE | `/admin/parking-spots/{spot_id}` | Deactivate parking spot |
| POST | `/admin/parking-spots/{spot_id}/ownerships` | Assign spot owner |
| GET | `/admin/parking-spots/{spot_id}/ownerships` | View ownership history |
| PATCH | `/admin/ownerships/{ownership_id}` | End or update ownership |

### 10.4 Availabilities

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/availabilities` | List open or filtered availabilities |
| POST | `/availabilities` | Publish owned spot availability |
| GET | `/availabilities/{availability_id}` | Get availability detail |
| PATCH | `/availabilities/{availability_id}/cancel` | Cancel own availability before assignment |
| GET | `/availabilities/mine` | List availabilities published by current user |
| GET | `/availabilities/{availability_id}/applications` | Owner/admin view applications |

Suggested filters for `GET /availabilities`:

- `status`
- `starts_from`
- `starts_to`
- `parking_spot_id`
- `team_priority_only`
- `location`

### 10.5 Applications

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/availabilities/{availability_id}/applications` | Apply for availability |
| GET | `/applications/mine` | List current user's applications |
| PATCH | `/applications/{application_id}/cancel` | Cancel own pending application |

### 10.6 Reservations

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/reservations/mine` | List current user's reservations |
| GET | `/reservations/{reservation_id}` | Get reservation detail |
| GET | `/admin/reservations` | Admin list all reservations |
| POST | `/admin/availabilities/{availability_id}/assign` | Admin manually assign winner |
| POST | `/admin/reservations/{reservation_id}/override` | Admin override existing reservation |

### 10.7 Example Request and Response Shapes

Create availability request:

```json
{
  "parking_spot_id": "spot-id",
  "starts_at": "2026-06-10T07:00:00Z",
  "ends_at": "2026-06-10T17:00:00Z",
  "note": "Available while I am visiting a client."
}
```

Availability response:

```json
{
  "id": "availability-id",
  "parking_spot": {
    "id": "spot-id",
    "code": "A-12",
    "location": "Main garage"
  },
  "owner": {
    "id": "owner-id",
    "full_name": "Owner Name",
    "team_id": "team-id"
  },
  "starts_at": "2026-06-10T07:00:00Z",
  "ends_at": "2026-06-10T17:00:00Z",
  "priority_window_ends_at": "2026-06-03T12:00:00Z",
  "status": "open",
  "note": "Available while I am visiting a client.",
  "current_user_application_status": null
}
```

## 11. Dockerization Plan

### 11.1 Services

Use Docker Compose with three main services:

- `postgres`: PostgreSQL database.
- `backend`: FastAPI app.
- `frontend`: Vue app.

Optional later services:

- `backend-worker`: Runs assignment scheduler separately from API.
- `redis`: Queue backend if Celery or RQ is introduced.

### 11.2 Backend Container

Backend image should:

- Use an official Python base image.
- Install dependencies from `requirements.txt` or `pyproject.toml`.
- Run Alembic migrations during deployment or through an explicit migration command.
- Start FastAPI through Uvicorn or Gunicorn with Uvicorn workers.

Required environment variables:

- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `JWT_ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `REFRESH_TOKEN_EXPIRE_DAYS`
- `CORS_ALLOWED_ORIGINS`
- `PRIORITY_WINDOW_HOURS`
- `FAIRNESS_ROLLING_DAYS`
- `FAIRNESS_SOFT_WIN_LIMIT`

### 11.3 Frontend Container

Frontend image should:

- Use Node for build stage.
- Build Vue static assets.
- Serve production assets with Nginx.
- Configure API base URL through environment configuration.

Development mode can run Vite directly.

### 11.4 PostgreSQL Container

PostgreSQL service should:

- Use a named Docker volume for persistence.
- Expose a local port only for development.
- Use environment variables for database name, user, and password.

### 11.5 Compose Layout

Planned files:

```text
docker-compose.yml
backend/Dockerfile
frontend/Dockerfile
frontend/nginx.conf
backend/.env.example
frontend/.env.example
```

Development compose behavior:

- Backend available at `http://localhost:8000`.
- Frontend available at `http://localhost:5173` or `http://localhost:8080`.
- PostgreSQL available at `localhost:5432`.

## 12. Implementation Phases

### Phase 1: Project Setup

Goals:

- Create backend and frontend project skeletons.
- Add Docker Compose.
- Configure PostgreSQL.
- Add basic health checks.

Tasks:

- Create backend FastAPI structure.
- Add dependency management.
- Configure SQLAlchemy and Alembic.
- Create frontend Vue project with Vite.
- Add Vue Router and Pinia.
- Add Dockerfiles and development compose file.
- Add `.env.example` files.
- Add basic CI-ready test commands.

### Phase 2: Authentication and User Management

Goals:

- Allow users to log in.
- Support admin-managed employees and teams.

Tasks:

- Implement user, team, and role models.
- Implement password hashing.
- Implement JWT login and current-user endpoint.
- Implement admin CRUD for users.
- Implement admin CRUD for teams.
- Add backend tests for authentication and permissions.
- Build login page.
- Build admin employees page.
- Build admin teams page.

### Phase 3: Parking Spot Management

Goals:

- Admins can manage parking spots and assign owners.

Tasks:

- Implement parking spot model.
- Implement parking spot ownership model.
- Add ownership history.
- Add admin APIs for parking spots and ownership.
- Add validation for one active owner per spot.
- Build admin parking spot page.
- Build owner spot list UI.

### Phase 4: Availability Publishing

Goals:

- Spot owners can publish availability.

Tasks:

- Implement availability model.
- Add overlap prevention.
- Implement publish availability service.
- Implement owner cancellation.
- Add APIs for creating and listing availabilities.
- Build publish availability form.
- Build available spots page.
- Add date/time handling and validation.

### Phase 5: Applications

Goals:

- Employees can apply and cancel applications.

Tasks:

- Implement application model.
- Add duplicate prevention.
- Add owner-cannot-apply validation.
- Implement application service.
- Implement application cancellation.
- Build apply button and application status UI.
- Build my applications page.
- Add tests for duplicate and invalid applications.

### Phase 6: Assignment and Fairness

Goals:

- Automatically assign parking spots according to priority and fairness rules.

Tasks:

- Implement reservation model.
- Implement assignment service.
- Implement priority window logic.
- Implement fairness ranking by recent wins and application timestamp.
- Implement soft win limit.
- Add assignment audit details.
- Add scheduled worker.
- Add tests for priority team selection.
- Add tests for fairness ranking.
- Add tests for no-applicant and late-application behavior.

### Phase 7: Admin Overrides and Audit

Goals:

- Admins can handle exceptions safely.

Tasks:

- Implement audit log model.
- Log cancellations, assignments, and overrides.
- Implement admin assignment endpoint.
- Implement admin reservation override endpoint.
- Build admin reservation view.
- Require override reason.
- Add tests for override permissions and audit logging.

### Phase 8: UI Polish and Reporting

Goals:

- Improve usability and provide clear operational visibility.

Tasks:

- Add dashboard summaries.
- Add status badges.
- Add filters and search.
- Add empty and loading states.
- Add responsive layout.
- Add reservation history views.
- Add optional export for admin reports.

### Phase 9: Production Readiness

Goals:

- Prepare the app for internal deployment.

Tasks:

- Harden CORS configuration.
- Add structured logging.
- Add error handling middleware.
- Add database backup guidance.
- Add deployment documentation.
- Add smoke tests.
- Add basic security review.
- Prepare SSO integration notes.

## 13. Detailed Task Breakdown

### 13.1 Backend Foundation

- Create `backend/app/main.py`.
- Add FastAPI app factory if needed.
- Add health endpoint `GET /health`.
- Add `backend/app/core/config.py` using Pydantic settings.
- Add database session configuration.
- Add base SQLAlchemy metadata.
- Configure Alembic.
- Create initial migration.
- Add test database configuration.

### 13.2 Models and Migrations

- Create `Team` model.
- Create `User` model.
- Create `ParkingSpot` model.
- Create `ParkingSpotOwnership` model.
- Create `ParkingAvailability` model.
- Create `ParkingApplication` model.
- Create `ParkingReservation` model.
- Create `AuditLog` model.
- Add indexes and constraints.
- Add Alembic migrations for each major domain group.

### 13.3 Auth and Permissions

- Implement password hashing utilities.
- Implement JWT creation.
- Implement JWT verification dependency.
- Implement current user dependency.
- Implement admin permission dependency.
- Implement ownership permission helper.
- Add login endpoint.
- Add refresh endpoint if refresh tokens are included.
- Add current-user endpoint.
- Add tests for invalid login, expired token, inactive user, and admin-only routes.

### 13.4 Admin Management

- Implement user repository and service.
- Implement team repository and service.
- Implement parking spot repository and service.
- Implement ownership repository and service.
- Add admin routers.
- Add pagination and search for admin lists.
- Add deactivate behavior instead of hard delete.
- Add tests for admin CRUD operations.

### 13.5 Availability Management

- Implement availability repository.
- Implement availability service.
- Validate active ownership.
- Validate date/time ranges.
- Validate no active overlap for the same spot.
- Calculate priority window.
- Add list filters.
- Add owner cancellation.
- Add status transitions.
- Add tests for publishing and cancellation.

### 13.6 Application Management

- Implement application repository.
- Implement application service.
- Validate open availability.
- Validate applicant is not owner.
- Validate applicant has no duplicate application.
- Implement cancellation.
- Add current-user application status in availability responses.
- Add tests for all validation rules.

### 13.7 Assignment Service

- Implement candidate loading.
- Implement same-team priority filtering.
- Implement recent-win counting.
- Implement soft win limit.
- Implement ranking.
- Implement reservation creation.
- Implement application status updates.
- Implement availability status update.
- Add row locking to prevent duplicate assignments.
- Add audit log entries.
- Add tests for concurrency-sensitive behavior where feasible.

### 13.8 Frontend Foundation

- Create Vue app.
- Configure router.
- Configure Pinia.
- Create API client.
- Create auth store.
- Create app layout.
- Create admin layout.
- Add protected routes.
- Add admin-only routes.
- Add reusable UI components.

### 13.9 Frontend Pages

- Build login page.
- Build dashboard page.
- Build available spots page.
- Build availability detail page.
- Build publish availability page.
- Build my applications page.
- Build my reservations page.
- Build admin employees page.
- Build admin teams page.
- Build admin parking spots page.
- Build admin reservations page.

### 13.10 Testing

Backend tests:

- Auth tests.
- Permission tests.
- Repository tests where useful.
- Service tests for business rules.
- API tests for main endpoints.
- Assignment fairness tests.

Frontend tests:

- Component tests for forms and status badges.
- Store tests for auth state.
- Route guard tests.
- Basic end-to-end tests for login, publish, apply, and assignment flow.

### 13.11 Documentation

- Add developer setup instructions.
- Add environment variable reference.
- Add database migration instructions.
- Add Docker Compose instructions.
- Add admin user creation instructions.
- Add fairness model explanation for admins.
- Add API documentation through FastAPI OpenAPI.

## 14. Key Risks and Mitigations

### Duplicate Assignment Risk

Risk:

- Two workers or requests assign the same availability at the same time.

Mitigation:

- Use database transactions.
- Lock availability rows during assignment.
- Use unique constraint on reservation availability ID.

### Overlapping Availability Risk

Risk:

- A spot owner publishes overlapping availability periods for the same spot.

Mitigation:

- Validate in service layer.
- Add PostgreSQL exclusion constraint for active overlap prevention.

### Perceived Unfairness

Risk:

- Employees may not understand why they did not win.

Mitigation:

- Use transparent ranking.
- Show high-level explanation in UI, such as "same-team priority window" and "recent wins considered".
- Provide admin audit detail.

### Manual Override Abuse

Risk:

- Admin override could be used without accountability.

Mitigation:

- Require override reason.
- Record audit logs.
- Show assignment method in admin views.

### Authentication Scope

Risk:

- Local password auth may not match company security expectations.

Mitigation:

- Start with JWT for MVP.
- Keep architecture ready for SSO/OIDC integration.

## 15. Recommended MVP Scope

The first MVP should include:

- JWT login.
- Employee and team management.
- Parking spot and ownership management.
- Publish availability.
- List available spots.
- Apply and cancel application.
- Automatic assignment after priority window.
- My applications.
- My reservations.
- Admin override.
- Basic audit logs.
- Docker Compose for local development.

Defer until later:

- SSO integration.
- Email or Teams notifications.
- Complex reporting.
- Weighted random selection.
- Mobile-specific app.
- Recurring availability templates.
- Multi-location advanced policy rules.

## 16. Acceptance Criteria for First Implementation Milestone

The first implementation milestone should be considered complete when:

- The application can run through Docker Compose.
- An admin can create a team, employee, parking spot, and ownership.
- A spot owner can publish availability.
- Another employee can apply.
- The owner cannot apply for their own spot.
- Duplicate applications are prevented.
- The assignment worker selects one winner after the priority window.
- Same-team priority is respected.
- Recent wins affect ranking.
- Availability closes after reservation.
- Admin can override an assignment with an audit reason.
- Main frontend pages are available and protected by authentication.

