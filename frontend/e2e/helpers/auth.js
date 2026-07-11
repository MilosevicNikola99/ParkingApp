import { expect } from "@playwright/test";

export async function login(page, credentials) {
  await page.goto("/login");
  await page.getByLabel("Username or email").fill(credentials.username);
  await page.getByLabel("Password").fill(credentials.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: "Dashboard", level: 1 })).toBeVisible();
}

export async function logout(page) {
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login$/);
}

export async function clearAuthentication(page) {
  await page.goto("/login");
  await page.evaluate(() => window.localStorage.clear());
  await page.reload();
  await expect(page).toHaveURL(/\/login$/);
}
