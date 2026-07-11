import { flushPromises, mount } from "@vue/test-utils";
import { ref } from "vue";
import { describe, expect, it, vi } from "vitest";

const teamService = vi.hoisted(() => ({
  createAdminTeam: vi.fn(),
  deleteAdminTeam: vi.fn(),
  listAdminTeams: vi.fn(),
  updateAdminTeam: vi.fn(),
}));

vi.mock("@/services/adminTeamService", () => teamService);
vi.mock("@/composables/useAuthenticatedPage", () => ({
  useAuthenticatedPage: () => ({
    currentUser: ref({ id: 1, first_name: "Ada", last_name: "Admin", role: "admin" }),
    handleLogout: vi.fn(),
  }),
}));

import AdminTeamsView from "./AdminTeamsView.vue";

const AppLayoutStub = { template: "<div><slot /></div>" };

describe("AdminTeamsView", () => {
  it("renders loaded teams and keeps deletion behind confirmation", async () => {
    teamService.listAdminTeams.mockResolvedValue([
      {
        id: 2,
        name: "Operations",
        description: "Facilities",
        updated_at: "2026-06-04T10:00:00Z",
      },
    ]);
    const wrapper = mount(AdminTeamsView, {
      global: { stubs: { AppLayout: AppLayoutStub } },
    });
    await flushPromises();

    expect(wrapper.text()).toContain("Operations");
    expect(wrapper.text()).toContain("Facilities");

    const deleteButton = wrapper.findAll("button").find((button) => button.text() === "Delete");
    await deleteButton.trigger("click");

    expect(teamService.deleteAdminTeam).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("Delete this team?");
  });
});
