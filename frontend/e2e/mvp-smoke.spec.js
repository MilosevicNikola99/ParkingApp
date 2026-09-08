import { expect, test } from "@playwright/test";

import { clearAuthentication, login, logout } from "./helpers/auth.js";
import { runDueAssignment } from "./helpers/assignment.js";

const requiredEnvironment = ["E2E_ADMIN_USERNAME", "E2E_ADMIN_PASSWORD", "E2E_USER_PASSWORD"];
for (const variableName of requiredEnvironment) {
  if (!process.env[variableName]) {
    throw new Error(`${variableName} is required. Use npm run e2e:docker for a disposable run.`);
  }
}

const runId = (process.env.E2E_RUN_ID || Date.now().toString(36)).replace(/[^A-Za-z0-9]/g, "");
const userPassword = process.env.E2E_USER_PASSWORD;
const credentials = {
  admin: {
    username: process.env.E2E_ADMIN_USERNAME,
    password: process.env.E2E_ADMIN_PASSWORD,
  },
  owner: { username: `e2e_owner_${runId}`, password: userPassword },
  employeeA: { username: `e2e_employee_a_${runId}`, password: userPassword },
  employeeB: { username: `e2e_employee_b_${runId}`, password: userPassword },
};
const names = {
  team: `E2E Team ${runId}`,
  ownerFirst: "E2EOwner",
  employeeAFirst: "E2EEmployeeA",
  employeeBFirst: "E2EEmployeeB",
  last: runId,
  spot: `E2E-SPOT-${runId}`,
  availabilityNote: `E2E availability ${runId}`,
};
const state = {};

function responseFor(path, method) {
  return (response) =>
    response.request().method() === method && new URL(response.url()).pathname === path;
}

async function createUser(page, { username, firstName, role, teamId }) {
  await page.getByLabel("Email").fill(`${username}@example.com`);
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("First name").fill(firstName);
  await page.getByLabel("Last name").fill(names.last);
  await page.getByLabel("Password").fill(userPassword);
  await page.getByLabel("Role").selectOption(role);
  await page.getByLabel("Team").selectOption(String(teamId));

  const responsePromise = page.waitForResponse(responseFor("/admin/users", "POST"));
  await page.getByRole("button", { name: "Create user" }).click();
  const response = await responsePromise;
  expect(response.status()).toBe(201);
  const user = await response.json();
  await expect(page.getByRole("alert")).toContainText(`User "${username}" saved.`);
  return user;
}

async function applyForRunAvailability(page) {
  await page.goto("/availabilities");
  const row = page.getByRole("row").filter({ hasText: names.availabilityNote });
  await expect(row).toBeVisible();
  const responsePromise = page.waitForResponse(responseFor("/parking-applications", "POST"));
  await row.getByRole("button", { name: "Apply" }).click();
  const response = await responsePromise;
  expect(response.status()).toBe(201);
  return response.json();
}

test.describe.serial("MVP browser smoke", () => {
  test("admin creates disposable team, users, and owned parking spot", async ({ page }) => {
    await login(page, credentials.admin);
    const adminNavigation = page.getByRole("navigation", { name: "Primary navigation" });
    await expect(adminNavigation).toContainText("Admin");
    await expect(adminNavigation).toContainText("Available spots");
    await expect(adminNavigation).toContainText("My requests");
    await expect(adminNavigation).toContainText("My reservations");
    state.admin = await page.evaluate(() => JSON.parse(localStorage.getItem("parking_app_current_user")));

    await page.goto("/admin/teams");
    await page.getByLabel("Name").fill(names.team);
    await page.getByLabel("Description").fill(`Disposable Playwright data ${runId}`);
    const teamResponsePromise = page.waitForResponse(responseFor("/admin/teams", "POST"));
    await page.getByRole("button", { name: "Create team" }).click();
    const teamResponse = await teamResponsePromise;
    expect(teamResponse.status()).toBe(201);
    state.team = await teamResponse.json();
    await expect(page.getByRole("alert")).toContainText('Team "' + names.team + '" saved.');

    await page.goto("/admin/users");
    state.owner = await createUser(page, {
      username: credentials.owner.username,
      firstName: names.ownerFirst,
      role: "parking_owner",
      teamId: state.team.id,
    });
    state.employeeA = await createUser(page, {
      username: credentials.employeeA.username,
      firstName: names.employeeAFirst,
      role: "employee",
      teamId: state.team.id,
    });
    state.employeeB = await createUser(page, {
      username: credentials.employeeB.username,
      firstName: names.employeeBFirst,
      role: "employee",
      teamId: state.team.id,
    });

    await page.goto("/admin/parking-spots");
    await page.getByLabel("Code").fill(names.spot);
    await page.getByLabel("Location").fill("E2E garage");
    await page.getByLabel("Description").fill("Disposable E2E spot " + runId);
    await page.getByLabel("Owner").first().selectOption(String(state.owner.id));
    const spotResponsePromise = page.waitForResponse(responseFor("/admin/parking-spots", "POST"));
    await page.getByRole("button", { name: "Create spot" }).click();
    const spotResponse = await spotResponsePromise;
    expect(spotResponse.status()).toBe(201);
    state.spot = await spotResponse.json();
    await expect(page.getByRole("alert")).toContainText('Parking spot "' + names.spot + '" saved.');

    await page.getByLabel("Code").fill(`E2E-ADMIN-${runId}`);
    await page.getByLabel("Location").fill("Admin garage");
    await page.getByLabel("Owner").first().selectOption(String(state.admin.id));
    const adminSpotResponsePromise = page.waitForResponse(responseFor("/admin/parking-spots", "POST"));
    await page.getByRole("button", { name: "Create spot" }).click();
    expect((await adminSpotResponsePromise).status()).toBe(201);
    await logout(page);
  });

  test("owner publishes future availability and sees it in own list", async ({ page }) => {
    await login(page, credentials.owner);
    await page.goto("/my-availabilities");

    const startAt = new Date(Date.now() + 4 * 60 * 60 * 1000);
    const endAt = new Date(Date.now() + 6 * 60 * 60 * 1000);
    const localValue = (value) => {
      const local = new Date(value.getTime() - value.getTimezoneOffset() * 60_000);
      return local.toISOString().slice(0, 16);
    };

    await expect(page.getByText(state.spot.code + " - " + state.spot.location)).toBeVisible();
    await expect(page.getByLabel("Parking spot ID")).toHaveCount(0);
    await page.getByLabel("Start").fill(localValue(startAt));
    await page.getByLabel("End").fill(localValue(endAt));
    await page.getByLabel("Note").fill(names.availabilityNote);
    const responsePromise = page.waitForResponse(responseFor("/parking-availabilities", "POST"));
    await page.getByRole("button", { name: "Publish offer" }).click();
    const response = await responsePromise;
    expect(response.status()).toBe(201);
    state.availability = await response.json();
    await expect(page.getByRole("alert")).toContainText(
      "Parking offer published for " + state.spot.code + " - " + state.spot.location + ".",
    );
    await expect(page.getByRole("row").filter({ hasText: names.availabilityNote })).toBeVisible();
  });
  test("employees apply and employee A receives scheduled assignment", async ({ page }) => {
    await login(page, credentials.employeeA);
    await expect(page.getByRole("navigation", { name: "Primary navigation" })).not.toContainText("Admin dashboard");
    state.applicationA = await applyForRunAvailability(page);
    await page.goto("/my-applications");
    await expect(page.getByRole("row").filter({ hasText: `Request #${state.applicationA.id}` })).toContainText("Waiting for assignment");
    await logout(page);

    await login(page, credentials.employeeB);
    state.applicationB = await applyForRunAvailability(page);
    await logout(page);

    expect(runDueAssignment()).toContain("assigned=1");

    await login(page, credentials.employeeA);
    await page.goto("/my-reservations");
    const reservationRow = page.getByRole("row").filter({ hasText: names.spot });
    await expect(reservationRow).toContainText("Active");
    state.reservationId = Number((await reservationRow.innerText()).match(/Reservation #(\d+)/)[1]);
  });

  test("admin validates and performs Employee ID replacement", async ({ page }) => {
    await login(page, credentials.admin);
    await page.goto("/admin/overrides");
    const replacement = page.getByRole("region", { name: "Replacement assignment" });

    await replacement.getByLabel("Availability ID").fill(String(state.availability.id));
    await replacement.getByLabel("Employee ID").fill(String(state.employeeB.id));
    await replacement.getByRole("button", { name: "Replace reservation" }).click();
    await expect(replacement.getByRole("alert")).toHaveText("Reason is required.");

    await replacement.getByLabel("Employee ID").fill("99999999");
    await replacement.getByLabel("Reason").fill("E2E invalid applicant validation");
    const invalidResponse = page.waitForResponse(
      responseFor(`/admin/parking-availabilities/${state.availability.id}/replace-reservation`, "POST"),
    );
    await replacement.getByRole("button", { name: "Replace reservation" }).click();
    expect((await invalidResponse).status()).toBe(404);
    await expect(page.getByRole("alert").filter({ hasText: "selected applicant" })).toBeVisible();

    await replacement.getByLabel("Employee ID").fill(String(state.employeeA.id));
    await replacement.getByLabel("Reason").fill("E2E current reservation validation");
    const currentResponse = page.waitForResponse(
      responseFor(`/admin/parking-availabilities/${state.availability.id}/replace-reservation`, "POST"),
    );
    await replacement.getByRole("button", { name: "Replace reservation" }).click();
    expect((await currentResponse).status()).toBe(409);
    await expect(page.getByRole("alert").filter({ hasText: "already has the active reservation" })).toBeVisible();

    await replacement.getByLabel("Employee ID").fill(String(state.employeeB.id));
    await replacement.getByLabel("Reason").fill(`E2E replacement ${runId}`);
    const replacementResponse = page.waitForResponse(
      responseFor(`/admin/parking-availabilities/${state.availability.id}/replace-reservation`, "POST"),
    );
    await replacement.getByRole("button", { name: "Replace reservation" }).click();
    const response = await replacementResponse;
    expect(response.status()).toBe(200);
    const reservation = await response.json();
    expect(reservation.id).toBe(state.reservationId);
    expect(reservation.reserved_for_user_id).toBe(state.employeeB.id);
    await expect(page.getByRole("alert").filter({ hasText: "replaced successfully" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Reservation summary" })).toContainText(
      `#${state.employeeB.id}`,
    );
  });

  test("replacement is reflected for employees and admin operational pages", async ({ page }) => {
    await login(page, credentials.employeeA);
    await page.goto("/my-reservations");
    await expect(page.getByText("No parking reservations")).toBeVisible();
    await logout(page);

    await login(page, credentials.employeeB);
    await page.goto("/my-reservations");
    await expect(page.getByRole("row").filter({ hasText: `Reservation #${state.reservationId}` })).toContainText("Active");
    await logout(page);

    await login(page, credentials.admin);
    await expect(page.getByRole("navigation", { name: "Primary navigation" })).toContainText("Offer my spot");
    await page.goto("/admin/reservations");
    const historyRow = page.getByRole("row").filter({ hasText: `#${state.reservationId}` });
    await expect(historyRow).toContainText(`#${state.employeeB.id}`);

    await page.goto("/admin/audit-logs");
    await page.getByLabel("Availability ID").fill(String(state.availability.id));
    await page.getByRole("button", { name: "Apply filters" }).click();
    const auditSection = page.getByRole("region", { name: "Assignment audit logs" });
    await expect(auditSection).toContainText("Admin override");
    await expect(auditSection).toContainText(`#${state.employeeB.id}`);
    await auditSection.getByText("Review decision details").first().click();
    await expect(auditSection).toContainText("Replacement");
    await expect(auditSection).toContainText(`E2E replacement ${runId}`);
    await expect(auditSection).toContainText("Technical details");

    await page.goto("/admin/reports");
    await expect(page.getByRole("region", { name: "Operational report summaries" })).toBeVisible();
    await expect(page.getByText("Total reservations")).toBeVisible();
  });

  test("protected routes, role navigation, and mobile override layout remain usable", async ({ page }) => {
    await clearAuthentication(page);
    await page.goto("/admin/overrides");
    await expect(page).toHaveURL(/\/login\?redirect=/);
    expect(new URL(page.url()).searchParams.get("redirect")).toBe("/admin/overrides");

    await page.getByLabel("Username or email").fill(credentials.employeeA.username);
    await page.getByLabel("Password").fill(credentials.employeeA.password);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByRole("navigation", { name: "Primary navigation" })).not.toContainText("Admin dashboard");
    await logout(page);

    await login(page, credentials.admin);
    await page.goto("/admin/overrides");
    const navigation = page.getByRole("navigation", { name: "Primary navigation" });
    const activeOverrideLink = navigation.getByRole("link", { name: "Overrides" });
    const requestsLink = navigation.getByRole("link", { name: "Requests", exact: true });
    const helpLink = navigation.getByRole("link", { name: "Help" });
    await expect(helpLink).toBeVisible();
    await helpLink.click();
    await expect(page).toHaveURL(/\/help$/);
    await expect(page.getByRole("heading", { name: "How to use ParkingApp" })).toBeVisible();
    await page.goto("/admin/overrides");
    await expect(activeOverrideLink).toHaveAttribute("aria-current", "page");
    await expect(activeOverrideLink).toHaveCSS("background-color", "rgb(255, 255, 255)");
    await expect(activeOverrideLink).toHaveCSS("color", "rgb(30, 58, 138)");
    await expect(requestsLink).toHaveCSS("color", "rgb(239, 246, 255)");

    const expandedAlignment = await navigation.evaluate((nav) => {
      const labels = ["Dashboard", "Help", "Admin dashboard", "Teams", "Requests", "Overrides"];
      return labels.map((label) => {
        const link = [...nav.querySelectorAll(".app-shell__nav-link")].find(
          (item) => item.querySelector(".app-shell__nav-label")?.textContent.trim() === label,
        );
        const icon = link.querySelector(".app-shell__nav-icon");
        const text = link.querySelector(".app-shell__nav-label");
        const linkBox = link.getBoundingClientRect();
        const iconBox = icon.getBoundingClientRect();
        const textBox = text.getBoundingClientRect();
        return {
          iconCenterDelta: Math.abs((linkBox.top + linkBox.height / 2) - (iconBox.top + iconBox.height / 2)),
          labelCenterDelta: Math.abs((linkBox.top + linkBox.height / 2) - (textBox.top + textBox.height / 2)),
          contained:
            iconBox.top >= linkBox.top && iconBox.bottom <= linkBox.bottom &&
            textBox.top >= linkBox.top && textBox.bottom <= linkBox.bottom,
          overflow: link.scrollWidth > link.clientWidth || link.scrollHeight > link.clientHeight,
        };
      });
    });
    for (const alignment of expandedAlignment) {
      expect(alignment.iconCenterDelta).toBeLessThanOrEqual(1);
      expect(alignment.labelCenterDelta).toBeLessThanOrEqual(1);
      expect(alignment.contained).toBe(true);
      expect(alignment.overflow).toBe(false);
    }

    await page.getByRole("button", { name: "Collapse sidebar navigation" }).click();
    await expect(page.locator(".app-shell")).toHaveClass(/app-shell--collapsed/);
    await expect(activeOverrideLink).toHaveAttribute("aria-label", "Overrides");
    expect(await page.evaluate(() => localStorage.getItem("parking-app-sidebar-collapsed"))).toBe("true");
    const compactAlignment = await activeOverrideLink.evaluate((link) => {
      const icon = link.querySelector(".app-shell__nav-icon");
      const linkBox = link.getBoundingClientRect();
      const iconBox = icon.getBoundingClientRect();
      return Math.abs((linkBox.left + linkBox.width / 2) - (iconBox.left + iconBox.width / 2));
    });
    expect(compactAlignment).toBeLessThanOrEqual(1);

    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/admin/overrides");
    await expect(page.getByRole("button", { name: "Replace reservation" })).toBeVisible();
    const hasPageOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    expect(hasPageOverflow).toBe(false);

    const replacement = page.getByRole("region", { name: "Replacement assignment" });
    await replacement.getByLabel("Availability ID").fill(String(state.availability.id));
    await replacement.getByLabel("Employee ID").fill(String(state.employeeA.id));
    await replacement.getByRole("button", { name: "Replace reservation" }).click();
    await expect(replacement.getByRole("alert")).toHaveText("Reason is required.");
    await expect(replacement.getByRole("alert")).toBeInViewport();
  });
});
