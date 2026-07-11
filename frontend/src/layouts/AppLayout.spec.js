import { mount, RouterLinkStub } from "@vue/test-utils";
import { beforeEach, describe, expect, it } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";

import AppLayout from "./AppLayout.vue";

function mountLayout(user) {
  return mount(AppLayout, {
    props: { user },
    global: { stubs: { RouterLink: RouterLinkStub } },
  });
}

describe("AppLayout navigation", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("shows admin navigation only to admin users", () => {
    const adminLayout = mountLayout({ first_name: "Ada", last_name: "Admin", role: "admin" });
    const employeeLayout = mountLayout({ first_name: "Eli", last_name: "Employee", role: "employee" });

    expect(adminLayout.text()).toContain("Admin dashboard");
    expect(adminLayout.text()).toContain("Parking spots");
    expect(adminLayout.text()).toContain("Audit logs");
    expect(adminLayout.text()).toContain("Reports");
    expect(employeeLayout.text()).not.toContain("Admin dashboard");
    expect(employeeLayout.text()).not.toContain("Audit logs");
    expect(employeeLayout.text()).not.toContain("Reports");
  });

  it("shows the Help entry for authenticated users", () => {
    const wrapper = mountLayout({ first_name: "Eli", last_name: "Employee", role: "employee" });

    expect(wrapper.text()).toContain("Help");
    expect(wrapper.findAllComponents(RouterLinkStub).some((link) => link.props("to") === "/help")).toBe(true);
  });

  it("collapses and persists sidebar state", async () => {
    const wrapper = mountLayout({ first_name: "Ada", last_name: "Admin", role: "admin" });

    await wrapper.get('button[aria-label="Collapse sidebar navigation"]').trigger("click");

    expect(wrapper.classes()).toContain("app-shell--collapsed");
    expect(localStorage.getItem("parking-app-sidebar-collapsed")).toBe("true");
    expect(wrapper.get('a[aria-label="Dashboard"]').attributes("title")).toBe("Dashboard");
  });

  it("identifies the active route when expanded and collapsed", async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: "/dashboard", component: { template: "<div />" } },
        { path: "/help", component: { template: "<div />" } },
        { path: "/:pathMatch(.*)*", component: { template: "<div />" } },
      ],
    });
    await router.push("/dashboard");
    await router.isReady();

    const wrapper = mount(AppLayout, {
      props: { user: { first_name: "Eli", last_name: "Employee", role: "employee" } },
      global: { plugins: [router] },
    });
    const dashboardLink = wrapper.get('.app-shell__nav-link[href="/dashboard"]');

    expect(dashboardLink.classes()).toContain("router-link-active");
    expect(dashboardLink.attributes("aria-current")).toBe("page");

    await wrapper.get('button[aria-label="Collapse sidebar navigation"]').trigger("click");

    expect(dashboardLink.classes()).toContain("router-link-active");
    expect(dashboardLink.attributes("aria-label")).toBe("Dashboard");
  });

  it("loads persisted collapsed sidebar state", () => {
    localStorage.setItem("parking-app-sidebar-collapsed", "true");
    const wrapper = mountLayout({ first_name: "Ada", last_name: "Admin", role: "admin" });

    expect(wrapper.classes()).toContain("app-shell--collapsed");
    expect(wrapper.get('button[aria-label="Expand sidebar navigation"]').exists()).toBe(true);
  });
});