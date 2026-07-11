import { beforeEach, describe, expect, it, vi } from "vitest";

const apiClient = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock("./apiClient", () => ({ default: apiClient }));

import {
  getAdminAssignmentAuditLog,
  getAdminAssignmentAuditLogByReservation,
  listAdminAssignmentAuditLogs,
} from "./adminAssignmentAuditLogService";
import {
  manualOverrideAssignment,
  replaceReservationAssignment,
} from "./adminReservationOverrideService";

describe("admin audit and override API services", () => {
  beforeEach(() => {
    apiClient.get.mockResolvedValue({ data: [] });
    apiClient.post.mockResolvedValue({ data: { id: 1 } });
  });

  it("builds assignment audit-log requests", async () => {
    await listAdminAssignmentAuditLogs({ availability_id: 2, trigger_source: "admin_override" });
    await getAdminAssignmentAuditLog(3);
    await getAdminAssignmentAuditLogByReservation(4);

    expect(apiClient.get).toHaveBeenNthCalledWith(1, "/admin/assignment-audit-logs", {
      params: { availability_id: 2, trigger_source: "admin_override" },
    });
    expect(apiClient.get).toHaveBeenNthCalledWith(2, "/admin/assignment-audit-logs/3");
    expect(apiClient.get).toHaveBeenNthCalledWith(3, "/admin/assignment-audit-logs/by-reservation/4");
  });

  it("calls the manual override endpoint with a trimmed reason", async () => {
    await manualOverrideAssignment(5, 6, "  Operational exception  ");

    expect(apiClient.post).toHaveBeenCalledWith(
      "/admin/parking-availabilities/5/override-assign",
      { application_id: 6, reason: "Operational exception" },
    );
  });

  it("calls the replacement override endpoint with a trimmed reason", async () => {
    await replaceReservationAssignment(7, 8, "  Reassign to selected applicant  ");

    expect(apiClient.post).toHaveBeenCalledWith(
      "/admin/parking-availabilities/7/replace-reservation",
      { application_id: 8, reason: "Reassign to selected applicant" },
    );
  });

  it("calls the replacement override endpoint with an applicant selector", async () => {
    await replaceReservationAssignment(7, { applicantId: 9 }, "  Reassign by applicant  ");

    expect(apiClient.post).toHaveBeenCalledWith(
      "/admin/parking-availabilities/7/replace-reservation",
      { applicant_id: 9, reason: "Reassign by applicant" },
    );
  });
});
