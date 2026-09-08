import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

import { login, logout } from "./helpers/auth.js";
import { runDueAssignment } from "./helpers/assignment.js";

if (process.env.USER_GUIDE_SCREENSHOTS !== "true") {
  throw new Error("USER_GUIDE_SCREENSHOTS=true is required. Use scripts/generate_user_guide_screenshots.ps1.");
}

const requiredEnvironment = ["E2E_ADMIN_USERNAME", "E2E_ADMIN_PASSWORD", "E2E_USER_PASSWORD"];
for (const variableName of requiredEnvironment) {
  if (!process.env[variableName]) {
    throw new Error(`${variableName} is required. Use scripts/generate_user_guide_screenshots.ps1.`);
  }
}

const screenshotDir = path.resolve(
  process.env.USER_GUIDE_SCREENSHOT_DIR || "../resources/docs/images/user_guide",
);
fs.mkdirSync(screenshotDir, { recursive: true });

const runId = (process.env.E2E_RUN_ID || "userguide").replace(/[^A-Za-z0-9]/g, "");
const userPassword = process.env.E2E_USER_PASSWORD;
const credentials = {
  admin: {
    username: process.env.E2E_ADMIN_USERNAME,
    password: process.env.E2E_ADMIN_PASSWORD,
  },
  owner: { username: `guide_owner_${runId}`, password: userPassword },
  employeeA: { username: `guide_employee_a_${runId}`, password: userPassword },
  employeeB: { username: `guide_employee_b_${runId}`, password: userPassword },
};
const names = {
  team: `QA Team ${runId}`,
  ownerFirst: "QAOwner",
  employeeAFirst: "QAEmployeeA",
  employeeBFirst: "QAEmployeeB",
  last: runId,
  spot: `QA-SPOT-${runId}`,
  availabilityNote: `QA availability ${runId}`,
};
const state = {};

function responseFor(pathname, method) {
  return (response) =>
    response.request().method() === method && new URL(response.url()).pathname === pathname;
}

async function capture(page, fileName, options = {}) {
  await page.screenshot({
    path: path.join(screenshotDir, fileName),
    fullPage: options.fullPage ?? true,
  });
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
  return response.json();
}

async function applyForAvailability(page) {
  await page.goto("/availabilities");
  const row = page.getByRole("row").filter({ hasText: names.availabilityNote });
  await expect(row).toBeVisible();
  const responsePromise = page.waitForResponse(responseFor("/parking-applications", "POST"));
  await row.getByRole("button", { name: "Apply" }).click();
  const response = await responsePromise;
  expect(response.status()).toBe(201);
  return response.json();
}

test.describe.serial("user guide screenshots", () => {
  test("capture login and admin setup screens", async ({ page }) => {
    await page.goto("/login");
    await capture(page, "login-page.png");

    await login(page, credentials.admin);
    state.admin = await page.evaluate(() => JSON.parse(localStorage.getItem("parking_app_current_user")));

    await page.goto("/admin/teams");
    await page.getByLabel("Name").fill(names.team);
    await page.getByLabel("Description").fill(`Disposable user guide data ${runId}`);
    const teamResponsePromise = page.waitForResponse(responseFor("/admin/teams", "POST"));
    await page.getByRole("button", { name: "Create team" }).click();
    const teamResponse = await teamResponsePromise;
    expect(teamResponse.status()).toBe(201);
    state.team = await teamResponse.json();
    await expect(page.getByRole("alert")).toContainText(`Team "${names.team}" saved.`);
    await capture(page, "admin-teams.png");

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
    await capture(page, "admin-users.png");

    await page.goto("/admin/parking-spots");
    await page.getByLabel("Code").fill(names.spot);
    await page.getByLabel("Location").fill("QA garage");
    await page.getByLabel("Description").fill(`Disposable guide spot ${runId}`);
    await page.getByLabel("Owner").first().selectOption(String(state.owner.id));
    const spotResponsePromise = page.waitForResponse(responseFor("/admin/parking-spots", "POST"));
    await page.getByRole("button", { name: "Create spot" }).click();
    const spotResponse = await spotResponsePromise;
    expect(spotResponse.status()).toBe(201);
    state.spot = await spotResponse.json();
    await expect(page.getByRole("alert")).toContainText(`Parking spot "${names.spot}" saved.`);

    await page.getByLabel("Code").fill(`QA-ADMIN-${runId}`);
    await page.getByLabel("Location").fill("Admin garage");
    await page.getByLabel("Owner").first().selectOption(String(state.admin.id));
    const adminSpotResponsePromise = page.waitForResponse(responseFor("/admin/parking-spots", "POST"));
    await page.getByRole("button", { name: "Create spot" }).click();
    expect((await adminSpotResponsePromise).status()).toBe(201);
    await capture(page, "admin-parking-spots.png");
    await logout(page);
  });

  test("capture owner availability screens", async ({ page }) => {
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
    await capture(page, "owner-publish-availability.png");

    const responsePromise = page.waitForResponse(responseFor("/parking-availabilities", "POST"));
    await page.getByRole("button", { name: "Publish offer" }).click();
    const response = await responsePromise;
    expect(response.status()).toBe(201);
    state.availability = await response.json();
    await expect(page.getByRole("row").filter({ hasText: names.availabilityNote })).toBeVisible();
    await capture(page, "owner-availability-list.png");
    await logout(page);
  });

  test("capture employee application and reservation screens", async ({ page }) => {
    await login(page, credentials.employeeA);
    await page.goto("/dashboard");
    await capture(page, "employee-dashboard.png");

    await page.goto("/availabilities");
    await expect(page.getByRole("row").filter({ hasText: names.availabilityNote })).toBeVisible();
    await capture(page, "employee-open-availabilities.png");

    state.applicationA = await applyForAvailability(page);
    await page.goto("/my-applications");
    await expect(page.getByRole("row").filter({ hasText: `Request #${state.applicationA.id}` })).toContainText("Waiting for assignment");
    await capture(page, "employee-applications.png");
    await logout(page);

    await login(page, credentials.employeeB);
    state.applicationB = await applyForAvailability(page);
    await logout(page);

    expect(runDueAssignment()).toContain("assigned=1");

    await login(page, credentials.employeeA);
    await page.goto("/my-reservations");
    const reservationRow = page.getByRole("row").filter({ hasText: names.spot });
    await expect(reservationRow).toContainText("Active");
    state.reservationId = Number((await reservationRow.innerText()).match(/Reservation #(\d+)/)[1]);
    await capture(page, "employee-reservations.png");
    await logout(page);
  });

  test("capture admin operational screens and mobile override layout", async ({ page }) => {
    await login(page, credentials.admin);

    await page.goto("/admin/parking-applications");
    await expect(page.getByRole("row", { name: new RegExp(`^#${state.applicationA.id}\\s`) })).toBeVisible();
    await capture(page, "admin-applications.png");

    await page.goto("/admin/reservations");
    await expect(page.getByRole("row").filter({ hasText: `#${state.reservationId}` })).toBeVisible();
    await capture(page, "admin-reservations.png");

    await page.goto("/admin/overrides");
    const replacement = page.getByRole("region", { name: "Replacement assignment" });
    await replacement.getByLabel("Availability ID").fill(String(state.availability.id));
    await replacement.getByLabel("Employee ID").fill(String(state.employeeB.id));
    await replacement.getByLabel("Reason").fill(`Guide replacement ${runId}`);
    const replacementResponse = page.waitForResponse(
      responseFor(`/admin/parking-availabilities/${state.availability.id}/replace-reservation`, "POST"),
    );
    await replacement.getByRole("button", { name: "Replace reservation" }).click();
    expect((await replacementResponse).status()).toBe(200);
    await expect(page.getByRole("alert").filter({ hasText: "replaced successfully" })).toBeVisible();
    await capture(page, "admin-overrides.png");

    await page.goto("/admin/audit-logs");
    await page.getByLabel("Availability ID").fill(String(state.availability.id));
    await page.getByRole("button", { name: "Apply filters" }).click();
    await expect(page.getByRole("region", { name: "Assignment audit logs" })).toContainText("Admin override");
    await page.getByText("Review decision details").first().click();
    await expect(page.getByText("Technical details").first()).toBeVisible();
    await capture(page, "admin-audit-logs.png");

    await page.goto("/admin/reports");
    await expect(page.getByRole("region", { name: "Operational report summaries" })).toBeVisible();
    await capture(page, "admin-reports.png");

    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/admin/overrides");
    await expect(page.getByRole("button", { name: "Replace reservation" })).toBeVisible();
    await capture(page, "mobile-admin-overrides.png");
  });
});
