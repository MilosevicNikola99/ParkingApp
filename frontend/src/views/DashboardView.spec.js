import { mount } from "@vue/test-utils";
import { ref } from "vue";
import { describe, expect, it, vi } from "vitest";

let role = "employee";

vi.mock("@/composables/useAuthenticatedPage", () => ({
  useAuthenticatedPage: () => ({
    currentUser: ref({ first_name: "Test", last_name: "User", role }),
    handleLogout: vi.fn(),
    sessionError: ref(""),
  }),
}));

import DashboardView from "./DashboardView.vue";

const stubs = {
  AppLayout: { template: "<div><slot /></div>" },
  DashboardCard: { props: ["title"], template: "<article>{{ title }}</article>" },
};

describe("DashboardView", () => {
  it.each([
    ["employee", ["Browse available spots", "Review my requests", "Review reservations"]],
    ["parking_owner", ["Offer your parking spot", "Review published offers"]],
    ["admin", ["People and parking", "Parking operations", "Audit activity", "Reports"]],
  ])("shows task-oriented cards for %s", (currentRole, expectedTitles) => {
    role = currentRole;
    const wrapper = mount(DashboardView, { global: { stubs } });

    for (const title of expectedTitles) expect(wrapper.text()).toContain(title);
  });
});
