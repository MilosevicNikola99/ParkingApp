import { flushPromises, mount } from "@vue/test-utils";
import { ref } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";

let role = "employee";
let userId = 1;

const parkingSpotService = vi.hoisted(() => ({ listMyActiveParkingSpots: vi.fn() }));
vi.mock("@/services/parkingSpotService", () => parkingSpotService);

vi.mock("@/composables/useAuthenticatedPage", () => ({
  useAuthenticatedPage: () => ({
    currentUser: ref({ id: userId, first_name: "Test", last_name: "User", role }),
    handleLogout: vi.fn(),
    sessionError: ref(""),
  }),
}));

import DashboardView from "./DashboardView.vue";
import AdminDashboardView from "./admin/AdminDashboardView.vue";

const stubs = {
  AppLayout: { template: "<div><slot /></div>" },
  DashboardCard: { props: ["title"], template: "<article>{{ title }}</article>" },
};

describe("DashboardView", () => {
  it("separates setup, operations, audit, and reporting with semantic headings", () => {
    const wrapper = mount(AdminDashboardView, { global: { stubs } });
    expect(wrapper.findAll("h2").map((heading) => heading.text())).toEqual([
      "Manage parking operations", "People and teams", "Parking spots", "Operations", "Audit", "Reporting",
    ]);
  });
  beforeEach(() => {
    userId += 1;
    parkingSpotService.listMyActiveParkingSpots.mockResolvedValue([]);
  });

  it.each([
    ["employee", ["Browse available spots", "Review my requests", "Review reservations"]],
    ["parking_owner", ["Browse available spots", "Review my requests", "Review reservations", "Offer your parking spot", "Review published offers"]],
    ["admin", ["Browse available spots", "Review my requests", "Review reservations", "People and parking", "Parking operations", "Audit activity", "Reports"]],
  ])("shows task-oriented cards for %s", async (currentRole, expectedTitles) => {
    role = currentRole;
    const wrapper = mount(DashboardView, { global: { stubs } });
    await flushPromises();

    for (const title of expectedTitles) expect(wrapper.text()).toContain(title);
  });

  it("adds owner tasks for an admin with an active owned spot", async () => {
    role = "admin";
    parkingSpotService.listMyActiveParkingSpots.mockResolvedValue([{ id: 12 }]);
    const wrapper = mount(DashboardView, { global: { stubs } });
    await flushPromises();

    expect(wrapper.text()).toContain("Offer your parking spot");
    expect(wrapper.text()).toContain("Review published offers");
    expect(wrapper.get('[aria-labelledby="dashboard-parking"]').text()).not.toContain("People and parking");
    expect(wrapper.get('[aria-labelledby="dashboard-offers"]').text()).toContain("Review published offers");
    expect(wrapper.get('[aria-labelledby="dashboard-admin"]').text()).toContain("People and parking");
  });
});
