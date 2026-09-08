import { flushPromises, mount, RouterLinkStub } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";

const parkingSpotService = vi.hoisted(() => ({ listMyActiveParkingSpots: vi.fn() }));
vi.mock("@/services/parkingSpotService", () => parkingSpotService);

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
    parkingSpotService.listMyActiveParkingSpots.mockResolvedValue([]);
  });

  it("shows normal parking navigation to admins while keeping the Admin section exclusive", async () => {
    const adminLayout = mountLayout({ id: 1, first_name: "Ada", last_name: "Admin", role: "admin" });
    const employeeLayout = mountLayout({ id: 2, first_name: "Eli", last_name: "Employee", role: "employee" });
    await flushPromises();

    expect(adminLayout.text()).toContain("Admin dashboard");
    expect(adminLayout.text()).toContain("Parking spots");
    expect(adminLayout.text()).toContain("Audit logs");
    expect(adminLayout.text()).toContain("Reports");
    expect(adminLayout.text()).toContain("Requests");
    expect(adminLayout.text()).toContain("Available spots");
    expect(adminLayout.text()).toContain("My requests");
    expect(adminLayout.text()).toContain("My reservations");
    expect(adminLayout.text()).not.toContain("Offer my spot");
    expect(employeeLayout.text()).not.toContain("Admin dashboard");
    expect(employeeLayout.text()).not.toContain("Audit logs");
    expect(employeeLayout.text()).not.toContain("Reports");
    expect(employeeLayout.text()).toContain("My requests");
    expect(employeeLayout.text()).not.toContain("Offer my spot");
  });

  it("shows normal and owner workflows to parking owners", async () => {
    const wrapper = mountLayout({ id: 3, first_name: "Olivia", last_name: "Owner", role: "parking_owner" });
    await flushPromises();

    expect(wrapper.text()).toContain("Offer my spot");
    expect(wrapper.text()).toContain("Available spots");
    expect(wrapper.text()).toContain("My requests");
    expect(wrapper.text()).toContain("My reservations");
  });

  it("shows Offer my spot to an admin or employee with an active owned spot", async () => {
    parkingSpotService.listMyActiveParkingSpots.mockResolvedValue([{ id: 9, is_active: true }]);
    const adminLayout = mountLayout({ id: 1, first_name: "Ada", last_name: "Admin", role: "admin" });
    const employeeLayout = mountLayout({ id: 2, first_name: "Eli", last_name: "Employee", role: "employee" });
    await flushPromises();

    expect(adminLayout.text()).toContain("Offer my spot");
    expect(employeeLayout.text()).toContain("Offer my spot");
    expect(parkingSpotService.listMyActiveParkingSpots).toHaveBeenCalledWith({ limit: 1 });
  });

  it("shows the Help entry for authenticated users", () => {
    const wrapper = mountLayout({ first_name: "Eli", last_name: "Employee", role: "employee" });

    expect(wrapper.text()).toContain("Help");
    expect(wrapper.findAllComponents(RouterLinkStub).some((link) => link.props("to") === "/help")).toBe(true);
  });

  it("renders meaningful decorative SVG icons while links keep accessible names", async () => {
    const wrapper = mountLayout({ id: 1, first_name: "Ada", last_name: "Admin", role: "admin" });
    await flushPromises();

    const links = wrapper.findAll(".app-shell__nav-link");
    expect(links.length).toBeGreaterThan(0);
    for (const link of links) {
      const icon = link.get("svg.navigation-icon");
      expect(icon.attributes("aria-hidden")).toBe("true");
      expect(icon.attributes("data-icon")).toBeTruthy();
      expect(link.get(".app-shell__nav-label").text()).toBeTruthy();
      expect(link.get(".app-shell__nav-icon").text()).toBe("");
    }

    const iconNames = wrapper.findAll("svg.navigation-icon").map((icon) => icon.attributes("data-icon"));
    expect(iconNames).toContain("dashboard");
    expect(iconNames).toContain("spots");
  });

  it("collapses and persists sidebar state", async () => {
    const wrapper = mountLayout({ first_name: "Ada", last_name: "Admin", role: "admin" });

    await wrapper.get('button[aria-label="Collapse sidebar navigation"]').trigger("click");

    expect(wrapper.classes()).toContain("app-shell--collapsed");
    expect(localStorage.getItem("parking-app-sidebar-collapsed")).toBe("true");
    expect(wrapper.get('a[aria-label="Dashboard"]').attributes("title")).toBe("Dashboard");
    expect(wrapper.get('a[aria-label="Dashboard"] .app-shell__nav-label').text()).toBe("Dashboard");
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

  it("opens mobile navigation independently of desktop collapse and closes it with Escape", async () => {
    localStorage.setItem("parking-app-sidebar-collapsed", "true");
    const wrapper = mountLayout({ id: 1, role: "admin" });
    const toggle = wrapper.get('button[aria-controls="primary-navigation"]');
    expect(toggle.attributes("aria-expanded")).toBe("false");
    await toggle.trigger("click");
    expect(toggle.attributes("aria-expanded")).toBe("true");
    expect(wrapper.get("nav").classes()).toContain("app-shell__nav--open");
    await wrapper.get("aside").trigger("keydown", { key: "Escape" });
    expect(toggle.attributes("aria-expanded")).toBe("false");
    expect(localStorage.getItem("parking-app-sidebar-collapsed")).toBe("true");
    expect(wrapper.get('.skip-link').attributes('href')).toBe('#main-content');
    expect(wrapper.get('main').attributes('tabindex')).toBe('-1');
  });
});
