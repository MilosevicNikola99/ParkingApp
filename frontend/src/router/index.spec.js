import { createMemoryHistory } from "vue-router";
import { describe, expect, it } from "vitest";

import { setAccessToken, setStoredCurrentUser } from "@/services/authStorage";

import { createAppRouter } from "./index";

describe("router authentication guards", () => {
  it("redirects unauthenticated users from protected routes to login", async () => {
    const router = createAppRouter(createMemoryHistory());

    await router.push("/my-reservations");
    await router.isReady();

    expect(router.currentRoute.value.name).toBe("login");
    expect(router.currentRoute.value.query.redirect).toBe("/my-reservations");
  });

  it("allows authenticated users to enter protected routes", async () => {
    setAccessToken("test-token");
    const router = createAppRouter(createMemoryHistory());

    await router.push("/availabilities");
    await router.isReady();

    expect(router.currentRoute.value.name).toBe("availabilities");
  });

  it("allows authenticated users to enter the help route", async () => {
    setAccessToken("test-token");
    const router = createAppRouter(createMemoryHistory());

    await router.push("/help");
    await router.isReady();

    expect(router.currentRoute.value.name).toBe("help");
  });

  it("redirects authenticated users away from login", async () => {
    setAccessToken("test-token");
    const router = createAppRouter(createMemoryHistory());

    await router.push("/login");
    await router.isReady();

    expect(router.currentRoute.value.name).toBe("dashboard");
  });

  it("allows authenticated admins to enter admin routes", async () => {
    setAccessToken("test-token");
    setStoredCurrentUser({ id: 1, role: "admin" });
    const router = createAppRouter(createMemoryHistory());

    await router.push("/admin/audit-logs");
    await router.isReady();

    expect(router.currentRoute.value.name).toBe("admin-audit-logs");
  });

  it("allows authenticated admins to enter the reports route", async () => {
    setAccessToken("test-token");
    setStoredCurrentUser({ id: 1, role: "admin" });
    const router = createAppRouter(createMemoryHistory());

    await router.push("/admin/reports");
    await router.isReady();

    expect(router.currentRoute.value.name).toBe("admin-reports");
  });

  it("redirects authenticated non-admin users away from admin routes", async () => {
    setAccessToken("test-token");
    setStoredCurrentUser({ id: 2, role: "employee" });
    const router = createAppRouter(createMemoryHistory());

    await router.push("/admin/overrides");
    await router.isReady();

    expect(router.currentRoute.value.name).toBe("dashboard");
  });
});