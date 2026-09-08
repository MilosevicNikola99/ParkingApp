import { flushPromises, mount } from "@vue/test-utils";
import { ref } from "vue";
import { describe, expect, it, vi } from "vitest";

const auditService = vi.hoisted(() => ({
  listAdminAssignmentAuditLogs: vi.fn(),
}));
const userService = vi.hoisted(() => ({ listAdminUsers: vi.fn() }));

vi.mock("@/services/adminAssignmentAuditLogService", () => auditService);
vi.mock("@/services/adminUserService", () => userService);
vi.mock("@/composables/useAuthenticatedPage", () => ({
  useAuthenticatedPage: () => ({
    currentUser: ref({ id: 1, first_name: "Ada", last_name: "Admin", role: "admin" }),
    handleLogout: vi.fn(),
  }),
}));

import AdminAssignmentAuditLogsView from "./AdminAssignmentAuditLogsView.vue";

const AppLayoutStub = { template: "<div><slot /></div>" };
const auditLog = {
  id: 10,
  availability_id: 11,
  reservation_id: 12,
  selected_application_id: 13,
  selected_user_id: 14,
  rejected_application_ids: [15, 16],
  ranking_policy: "same_team_then_created",
  ranking_details: [{ action: "replacement", application_id: 13, selected_user_id: 14, admin_user_id: 1, override_reason: "Support correction", explanation: "<script>unsafe()</script>" }],
  trigger_source: "admin_override",
  created_at: "2026-06-04T10:00:00Z",
};

describe("AdminAssignmentAuditLogsView", () => {
  it("renders audit rows and safely formatted ranking details", async () => {
    auditService.listAdminAssignmentAuditLogs.mockResolvedValue([auditLog]);
    userService.listAdminUsers.mockResolvedValue([
      { id: 1, first_name: "Ada", last_name: "Admin", email: "ada@example.com" },
      { id: 14, first_name: "Erin", last_name: "Employee", email: "erin@example.com" },
    ]);
    const wrapper = mount(AdminAssignmentAuditLogsView, {
      global: { stubs: { AppLayout: AppLayoutStub } },
    });
    await flushPromises();

    expect(wrapper.text()).toContain("#10");
    expect(wrapper.text()).toContain("same_team_then_created");
    expect(wrapper.text()).toContain("Erin Employee");
    expect(wrapper.text()).toContain("Support correction");
    expect(wrapper.text()).toContain("Technical details");
    expect(wrapper.text()).toContain('"application_id": 13');
    expect(wrapper.text()).toContain("<script>unsafe()</script>");
    expect(wrapper.html()).not.toContain("<script>unsafe()</script>");
    expect(wrapper.html()).toContain("&lt;script&gt;unsafe()&lt;/script&gt;");
  });

  it("calls the service with normalized filter parameters", async () => {
    auditService.listAdminAssignmentAuditLogs.mockResolvedValue([]);
    userService.listAdminUsers.mockResolvedValue([]);
    const wrapper = mount(AdminAssignmentAuditLogsView, {
      global: { stubs: { AppLayout: AppLayoutStub } },
    });
    await flushPromises();

    await wrapper.get('input[name="audit-availability-filter"]').setValue("11");
    await wrapper.get('input[name="audit-reservation-filter"]').setValue("12");
    await wrapper.get('input[name="audit-user-filter"]').setValue("14");
    await wrapper.get('select[name="audit-trigger-filter"]').setValue("admin_override");
    await wrapper.get('input[name="audit-policy-filter"]').setValue("  same_team_then_created  ");
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    expect(auditService.listAdminAssignmentAuditLogs).toHaveBeenLastCalledWith({
      availability_id: 11,
      reservation_id: 12,
      selected_user_id: 14,
      trigger_source: "admin_override",
      ranking_policy: "same_team_then_created",
    });
    expect(userService.listAdminUsers).toHaveBeenLastCalledWith({ limit: 1000 });
  });
});
