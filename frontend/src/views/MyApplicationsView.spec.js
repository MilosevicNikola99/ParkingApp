import { flushPromises, mount } from "@vue/test-utils";
import { ref } from "vue";
import { describe, expect, it, vi } from "vitest";

const applicationService = vi.hoisted(() => ({
  cancelApplication: vi.fn(),
  listMyApplications: vi.fn(),
}));

vi.mock("@/services/applicationService", () => applicationService);
vi.mock("@/composables/useAuthenticatedPage", () => ({
  useAuthenticatedPage: () => ({
    currentUser: ref({ id: 1, first_name: "Erin", last_name: "Employee", role: "employee" }),
    handleLogout: vi.fn(),
  }),
}));

import MyApplicationsView from "./MyApplicationsView.vue";

describe("MyApplicationsView", () => {
  it("presents requests with spot context and secondary references", async () => {
    applicationService.listMyApplications.mockResolvedValue([{
      id: 17,
      availability_id: 11,
      status: "pending",
      note: null,
      created_at: "2026-08-20T08:00:00Z",
      availability: {
        id: 11,
        start_at: "2026-08-21T08:00:00Z",
        end_at: "2026-08-21T12:00:00Z",
        parking_spot: { id: 4, code: "A-04", location: "East garage" },
      },
    }]);

    const wrapper = mount(MyApplicationsView, {
      global: { stubs: { AppLayout: { template: "<div><slot /></div>" } } },
    });
    await flushPromises();

    expect(wrapper.text()).toContain("My parking requests");
    expect(wrapper.text()).toContain("A-04 - East garage");
    expect(wrapper.text()).toContain("Waiting for assignment");
    expect(wrapper.text()).toContain("Request #17 · Offer #11");
  });
});
