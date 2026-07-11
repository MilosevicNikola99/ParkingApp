import { flushPromises, mount } from "@vue/test-utils";
import { ref } from "vue";
import { describe, expect, it, vi } from "vitest";

const auditService = vi.hoisted(() => ({
  listAdminAssignmentAuditLogs: vi.fn(),
}));

vi.mock("@/services/adminAssignmentAuditLogService", () => auditService);
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
  ranking_details: [{ application_id: 13, explanation: "<script>unsafe()</script>" }],
  trigger_source: "admin_override",
  created_at: "2026-06-04T10:00:00Z",
};

describe("AdminAssignmentAuditLogsView", () => {
  it("renders audit rows and safely formatted ranking details", async () => {
    auditService.listAdminAssignmentAuditLogs.mockResolvedValue([auditLog]);
    const wrapper = mount(AdminAssignmentAuditLogsView, {
      global: { stubs: { AppLayout: AppLayoutStub } },
    });
    await flushPromises();

    expect(wrapper.text()).toContain("#10");
    expect(wrapper.text()).toContain("same_team_then_created");
    expect(wrapper.text()).toContain('"application_id": 13');
    expect(wrapper.text()).toContain("<script>unsafe()</script>");
    expect(wrapper.html()).not.toContain("<script>unsafe()</script>");
    expect(wrapper.html()).toContain("&lt;script&gt;unsafe()&lt;/script&gt;");
  });

  it("calls the service with normalized filter parameters", async () => {
    auditService.listAdminAssignmentAuditLogs.mockResolvedValue([]);
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
  });
});
