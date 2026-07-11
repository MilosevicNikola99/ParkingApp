# ParkingApp User Guide

This guide explains how to use ParkingApp from the browser. It is written for everyday users and covers the three roles in the application:

- Employee
- Parking owner
- Administrator

Use the web address provided by your company administrator. In a local training setup, the application is usually opened at `http://localhost:8080`.

## 1. About ParkingApp

ParkingApp helps employees request available parking, parking owners publish temporary parking availability, and administrators manage the people, teams, parking spots, assignments, and reports.

The normal flow is:

1. An administrator creates teams, users, and parking spots.
2. A parking owner publishes an available parking time window.
3. Employees apply for the available spot.
4. The assignment process selects an employee and creates a reservation.
5. Employees and administrators review the reservation history.

## 2. Accessing The Application

Open ParkingApp in your browser and sign in with your username or email and password.

![Login page](images/user_guide/login-page.png)

If sign-in succeeds, you will see the Dashboard. If sign-in fails, check the username or email and password and try again. The application shows `Invalid credentials.` when the username, email, or password is not accepted.

Do not share your password with another user. If you cannot sign in, contact your administrator.

## 3. General Navigation

The main navigation is visible after sign-in. All signed-in users can see:

- Dashboard
- Available spots
- My availabilities
- My applications
- My reservations
- Help

Administrators also see the Admin section:

- Admin dashboard
- Teams
- Users
- Parking spots
- Applications
- Reservations
- Audit logs
- Overrides
- Reports

The Dashboard gives quick links into the main areas for your role. Use **Help** for quick role-specific steps. On desktop, the sidebar can be collapsed or expanded; the application remembers your choice on the same browser.

![Employee dashboard](images/user_guide/employee-dashboard.png)

Use **Sign out** when you finish using the application, especially on a shared computer.

## 4. Employee Guide

Employees use ParkingApp to find available parking, apply for a spot, review applications, and view or cancel active reservations.

### View Available Spots

Open **Available spots** to see parking availability that can still receive applications.

![Available spots](images/user_guide/employee-open-availabilities.png)

Choose **Apply** on the row you want. If the application is accepted, it appears in **My applications**.

Common situations:

- If you already applied for that availability, the application shows `You already applied for this availability.`
- If the availability is no longer open, the application shows `This parking availability is no longer open.`

### Review My Applications

Open **My applications** to see your application history and current status.

![My applications](images/user_guide/employee-applications.png)

Application statuses:

- `pending`: your request is waiting for assignment.
- `selected`: your request was selected for a reservation.
- `cancelled`: your request was cancelled.
- `rejected`: your request was not selected.

Pending applications can be cancelled from this screen when the cancel action is available.

### Review My Reservations

Open **My reservations** to see parking that has been assigned to you.

![My reservations](images/user_guide/employee-reservations.png)

Reservation statuses:

- `active`: the reservation is currently assigned to you.
- `cancelled`: the reservation was cancelled.
- `completed`: the reservation has ended or was completed.

If cancellation is available for an active reservation, enter a reason if needed and choose the cancel action. After cancellation, the reservation history remains visible.

## 5. Parking Owner Guide

Parking owners publish availability for parking spots assigned to them by an administrator.

The app loads active parking spots assigned to your account. If you have one active spot, it is shown and selected automatically. If you have more than one, choose the spot from the list.

### Publish Availability

Open **My availabilities**, verify or select your assigned parking spot, enter the start time, end time, and an optional note, then choose **Publish**. You never need to type an internal parking spot ID.

If no active parking spot is shown, contact an administrator and ask them to review your parking spot assignment.

![Publish availability](images/user_guide/owner-publish-availability.png)

If the time range overlaps another availability for the same spot, the application shows `This time range overlaps another availability for the parking spot.`

### Review My Availabilities

After publishing, the availability appears in your list.

![My availabilities](images/user_guide/owner-availability-list.png)

Availability statuses:

- `open`: employees can apply.
- `assigned`: an employee has been assigned.
- `cancelled`: the availability was cancelled.
- `expired`: the availability was no longer usable before assignment.

The current owner screen focuses on your published availability records. It does not show full employee reservation details; use your administrator if you need operational history.

## 6. Administrator Guide

Administrators manage setup data, review activity, perform controlled overrides, and export reports.

### Manage Teams

Open **Teams** to create or update teams.

![Admin teams](images/user_guide/admin-teams.png)

Teams help group employees and can influence assignment priority while the configured priority window is active.

### Manage Users

Open **Users** to create employee, parking owner, and administrator accounts.

![Admin users](images/user_guide/admin-users.png)

Choose the role carefully:

- `admin`: can manage setup, operations, overrides, audit logs, and reports.
- `employee`: can apply for parking and manage their own applications and reservations.
- `parking_owner`: can publish availability for assigned parking spots.

Use active status for accounts that should be allowed to sign in. Inactive users cannot use the application.

### Manage Parking Spots

Open **Parking spots** to create parking spot records and assign an owner.

![Admin parking spots](images/user_guide/admin-parking-spots.png)

Give the parking owner the spot ID when they need to publish availability.

### Review Applications

Open **Applications** to review employee application activity.

![Admin applications](images/user_guide/admin-applications.png)

Use this screen to inspect application IDs, availability IDs, applicants, statuses, and timestamps. These IDs are useful when performing manual overrides.

### Review Reservations

Open **Reservations** to review reservation history and current active assignments.

![Admin reservations](images/user_guide/admin-reservations.png)

The browser Reservations screen is currently a history and review screen. Admin override actions are handled from **Overrides**.

### Use Overrides

Open **Overrides** when an administrator must manually assign or replace a reservation. A reason is required so the decision can be audited.

![Admin overrides](images/user_guide/admin-overrides.png)

For replacement assignments, provide either:

- Application ID, or
- Applicant ID

Use only one of those fields for a replacement. If the reason is missing, the application shows `Reason is required.`

The mobile layout keeps the same controls available on a narrow screen.

![Mobile admin overrides](images/user_guide/mobile-admin-overrides.png)

### Review Audit Logs

Open **Audit logs** to review assignment decisions and admin overrides.

![Admin audit logs](images/user_guide/admin-audit-logs.png)

Audit logs are useful when checking why a reservation was created or changed.

### Review Reports And Exports

Open **Reports** to review operational summaries and export CSV files.

![Admin reports](images/user_guide/admin-reports.png)

Available exports include:

- reservations
- availabilities
- applications
- audit logs

## 7. Status Reference

### Availability Statuses

| Status | Meaning |
| --- | --- |
| `open` | Employees can apply. |
| `assigned` | A reservation was created from this availability. |
| `cancelled` | The availability was cancelled. |
| `expired` | The availability expired before assignment. |

### Application Statuses

| Status | Meaning |
| --- | --- |
| `pending` | The application is waiting for assignment. |
| `selected` | The application was selected for a reservation. |
| `cancelled` | The application was cancelled. |
| `rejected` | The application was not selected. |

### Reservation Statuses

| Status | Meaning |
| --- | --- |
| `active` | The parking reservation is currently assigned. |
| `cancelled` | The parking reservation was cancelled. |
| `completed` | The parking reservation is completed. |

## 8. Common Messages And What They Mean

| Message | What to do |
| --- | --- |
| `Invalid credentials.` | Check the username or email and password, then try again. |
| `Your session has expired. Sign in again.` | Sign in again. |
| `You do not have permission to perform this action.` | Use an account with the required role or contact an administrator. |
| `You already applied for this availability.` | Review the existing request in **My applications**. |
| `This parking availability is no longer open.` | Choose a different available spot. |
| `This time range overlaps another availability for the parking spot.` | Choose a different time range. |
| `The selected applicant already has the active reservation.` | Choose another applicant or review the current reservation. |
| `Enter a reason for the reservation override.` | Add a clear reason before submitting the override. |
| `The parking record changed and the action could not be completed.` | Refresh the page and try again. |
| `Check the entered values and try again.` | Review required fields and values. |

If you contact support, include what you were trying to do, the date and time, your role, the page name, and any visible message. If a support person asks for a request ID and one is available, include it.

## 9. Troubleshooting

### I Cannot Sign In

Check that you are using the correct username or email. If the password is still not accepted, ask an administrator to check that your account is active.

### I Cannot See Admin Pages

Only administrators can access the Admin section. If you need administrator access, contact the person responsible for ParkingApp user management.

### I Cannot Publish Availability

Confirm that you are signed in as a parking owner and that your assigned active parking spot appears on **My availabilities**. If no spot appears, ask an administrator to review the parking spot assignment and status.

### I Cannot Apply For A Spot

The availability may no longer be open, you may have already applied, or the spot may have been assigned. Refresh **Available spots** and check **My applications**.

### My Reservation Disappeared From Active Reservations

The reservation may have been cancelled, completed, or replaced by an administrator. Check **My reservations** and contact an administrator if the history is unclear.

### A Page Looks Wrong On Mobile

Refresh the page first. If the issue remains, record the page name, your device or browser, and what looked wrong, then contact support.

## 10. Quick-Reference Workflows

### Employee Applies For Parking

1. Sign in.
2. Open **Available spots**.
3. Choose **Apply** on an open availability.
4. Open **My applications** to confirm the request is listed.
5. Open **My reservations** after assignment to see the result.

### Parking Owner Publishes Availability

1. Sign in.
2. Open **My availabilities**.
3. Verify the assigned spot shown by the app, or select one of your assigned spots.
4. Enter Start, End, and an optional Note.
5. Choose **Publish**.
6. Confirm the availability appears in the list.

### Administrator Sets Up A New Parking Flow

1. Open **Teams** and create the team.
2. Open **Users** and create the employee and parking owner.
3. Open **Parking spots** and assign a spot to the parking owner.
4. Ask the parking owner to publish availability.
5. Review **Applications**, **Reservations**, **Audit logs**, and **Reports** as needed.

### Administrator Replaces A Reservation

1. Open **Applications** or **Reservations** to find the needed IDs.
2. Open **Overrides**.
3. Enter Availability ID.
4. Enter either Application ID or Applicant ID.
5. Enter a reason.
6. Choose **Replace reservation**.
7. Check **Reservations** and **Audit logs**.
