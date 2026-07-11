import { defineConfig, devices } from "@playwright/test";

const useLocalNoSandbox = process.env.E2E_DISABLE_SANDBOX === "true";
const isCi = Boolean(process.env.CI);

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  workers: 1,
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  outputDir: "test-results",
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "playwright-report" }],
  ],
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:8080",
    actionTimeout: 10_000,
    navigationTimeout: 30_000,
    screenshot: "only-on-failure",
    trace: isCi ? "off" : "retain-on-failure",
    video: isCi ? "off" : "retain-on-failure",
    launchOptions: useLocalNoSandbox
      ? { args: ["--no-sandbox", "--disable-setuid-sandbox"] }
      : undefined,
  },
  projects: [
    {
      name: "chromium-desktop",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
