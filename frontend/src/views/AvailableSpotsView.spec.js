import { flushPromises, mount, RouterLinkStub } from "@vue/test-utils";
import { ref } from "vue";
import { describe, expect, it, vi } from "vitest";

const applicationService = vi.hoisted(() => ({
  applyForAvailability: vi.fn(),
}));
const availabilityService = vi.hoisted(() => ({
  listOpenAvailabilities: vi.fn(),
}));

vi.mock("@/services/applicationService", () => applicationService);
vi.mock("@/services/availabilityService", () => availabilityService);
vi.mock("@/composables/useAuthenticatedPage", () => ({
  useAuthenticatedPage: () => ({
    currentUser: ref({ id: 1, first_name: "Employee", last_name: "User" }),
    handleLogout: vi.fn(),
  }),
}));

import AvailableSpotsView from "./AvailableSpotsView.vue";

const AppLayoutStub = {
  template: "<div><slot /></div>",
};

describe("AvailableSpotsView", () => {
  it("prevents duplicate rapid application submissions", async () => {
    availabilityService.listOpenAvailabilities.mockResolvedValue([
      {
        id: 7,
        parking_spot_id: 22,
        owner_id: 2,
        start_at: "2026-06-10T10:00:00Z",
        end_at: "2026-06-10T12:00:00Z",
        priority_until: null,
        status: "open",
        note: null,
        parking_spot: { id: 22, code: "A-22", location: "North garage" },
        owner: { id: 2, first_name: "Olivia", last_name: "Owner", email: "owner@example.com" },
      },
    ]);
    let resolveApplication;
    applicationService.applyForAvailability.mockImplementation(
      () => new Promise((resolve) => {
        resolveApplication = resolve;
      }),
    );
    const wrapper = mount(AvailableSpotsView, {
      global: { stubs: { AppLayout: AppLayoutStub } },
    });
    await flushPromises();

    expect(wrapper.get(".person-cell__name").text()).toBe("Olivia Owner");
    expect(wrapper.get(".person-cell__email").text()).toBe("owner@example.com");
    expect(wrapper.text()).not.toContain("Olivia Owner (owner@example.com)");

    const applyButton = wrapper.findAll("button").find((button) => button.text() === "Apply");
    await applyButton.trigger("click");
    await applyButton.trigger("click");

    expect(applicationService.applyForAvailability).toHaveBeenCalledTimes(1);

    resolveApplication({ id: 20 });
    await flushPromises();
    expect(wrapper.text()).toContain("Requested");
    expect(wrapper.text()).toContain("Parking request submitted for A-22 - North garage.");
  });

  it("renders the empty state with guidance", async () => {
    availabilityService.listOpenAvailabilities.mockResolvedValue([]);
    const wrapper = mount(AvailableSpotsView, {
      global: { stubs: { AppLayout: AppLayoutStub, RouterLink: RouterLinkStub } },
    });
    await flushPromises();

    expect(wrapper.text()).toContain("No open spots");
    expect(wrapper.text()).toContain("No parking spots are available right now.");
    expect(wrapper.text()).toContain("Check again later");
  });
});
