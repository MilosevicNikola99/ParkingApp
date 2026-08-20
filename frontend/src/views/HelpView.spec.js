import { mount } from "@vue/test-utils";
import { ref } from "vue";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/composables/useAuthenticatedPage", () => ({
  useAuthenticatedPage: () => ({
    currentUser: ref({ id: 1, first_name: "Ada", last_name: "Admin", role: "admin" }),
    handleLogout: vi.fn(),
  }),
}));

import HelpView from "./HelpView.vue";

const AppLayoutStub = { template: "<div><slot /></div>" };

describe("HelpView", () => {
  it("renders role-specific quick-start guidance", () => {
    const wrapper = mount(HelpView, {
      global: { stubs: { AppLayout: AppLayoutStub } },
    });

    expect(wrapper.text()).toContain("Employee");
    expect(wrapper.text()).toContain("Parking owner");
    expect(wrapper.text()).toContain("Administrator");
    expect(wrapper.text()).toContain("Request parking");
    expect(wrapper.text()).toContain("Offer a parking spot");
    expect(wrapper.text()).toContain("Manage operations");
  });
});
