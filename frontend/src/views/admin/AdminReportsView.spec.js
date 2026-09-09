import { flushPromises, mount } from "@vue/test-utils";
import { ref } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";

const reportService = vi.hoisted(() => ({
  downloadReportCsv: vi.fn(),
  getParkingSpotUsage: vi.fn(),
  getSummaryReport: vi.fn(),
  getTopUsers: vi.fn(),
}));
const userService = vi.hoisted(() => ({ listAdminUsers: vi.fn() }));
const parkingSpotService = vi.hoisted(() => ({ listAdminParkingSpots: vi.fn() }));

vi.mock("@/services/adminReportService", () => reportService);
vi.mock("@/services/adminUserService", () => userService);
vi.mock("@/services/adminParkingSpotService", () => parkingSpotService);
vi.mock("@/composables/useAuthenticatedPage", () => ({
  useAuthenticatedPage: () => ({
    currentUser: ref({ id: 1, first_name: "Ada", last_name: "Admin", role: "admin" }),
    handleLogout: vi.fn(),
  }),
}));

import AdminReportsView from "./AdminReportsView.vue";

const AppLayoutStub = { template: "<div><slot /></div>" };
const summary = {
  reservation_summary: { total: 8, active: 4, cancelled: 2, completed: 2 },
  availability_summary: {
    total: 10,
    open: 3,
    assigned: 4,
    cancelled: 2,
    expired: 1,
    open_without_reservation: 2,
  },
  application_summary: { total: 14, pending: 4, selected: 4, rejected: 3, cancelled: 3 },
  audit_trigger_summary: [
    { trigger_source: "scheduled", count: 5 },
    { trigger_source: "admin_override", count: 2 },
  ],
};

function mountReports() {
  return mount(AdminReportsView, {
    global: { stubs: { AppLayout: AppLayoutStub } },
  });
}

describe("AdminReportsView", () => {
  beforeEach(() => {
    reportService.getSummaryReport.mockResolvedValue(summary);
    reportService.getTopUsers.mockResolvedValue([{ user_id: 7, reservation_count: 3 }]);
    reportService.getParkingSpotUsage.mockResolvedValue([{ parking_spot_id: 9, reservation_count: 4 }]);
    reportService.downloadReportCsv.mockResolvedValue(undefined);
    userService.listAdminUsers.mockResolvedValue([
      { id: 7, first_name: "Erin", last_name: "Employee", email: "erin@example.com" },
    ]);
    parkingSpotService.listAdminParkingSpots.mockResolvedValue([
      { id: 9, code: "A-09", location: "East garage", description: "Near the lift" },
    ]);
  });

  it("renders summaries, rankings, audit triggers, and CSV export actions", async () => {
    const wrapper = mountReports();
    await flushPromises();

    expect(wrapper.text()).toContain("Total reservations");
    expect(wrapper.text()).toContain("Open without reservation");
    expect(wrapper.text()).toContain("Cancelled reservations");
    expect(wrapper.text()).toContain("Request lifecycle");
    expect(wrapper.text()).toContain("Open for requests");
    expect(wrapper.text()).toContain("Waiting for assignment");
    expect(wrapper.text()).toContain("Not selected");
    expect(wrapper.text()).not.toMatch(/\bPending\b|\bRejected\b/);
    expect(wrapper.text()).not.toContain("User #7");
    expect(wrapper.text()).toContain("Erin Employee");
    expect(wrapper.text()).toContain("erin@example.com");
    expect(wrapper.text()).toContain("A-09");
    expect(wrapper.text()).toContain("East garage");
    expect(wrapper.text()).not.toContain("Spot #9");
    expect(wrapper.text()).not.toContain("Parking spot reference");
    expect(wrapper.findAll(".report-list-header").map((header) => header.text())).toEqual([
      "UserReservations",
      "Parking spotReservations",
      "Trigger sourceEvents",
    ]);
    expect(wrapper.text()).toContain("Scheduled");
    expect(wrapper.text()).toContain("Export reservations");
    expect(wrapper.text()).toContain("Export audit logs");
    expect(wrapper.findAll(".report-compact-list")).toHaveLength(2);
    expect(wrapper.find(".report-trigger-list").exists()).toBe(true);
    expect(wrapper.find(".report-breakdown-grid table").exists()).toBe(false);
  });

  it("submits created-date filters to all report endpoints", async () => {
    const wrapper = mountReports();
    await flushPromises();

    await wrapper.get('input[name="report-date-from"]').setValue("2026-06-01");
    await wrapper.get('input[name="report-date-to"]').setValue("2026-06-30");
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    const params = { date_from: "2026-06-01", date_to: "2026-06-30" };
    expect(reportService.getSummaryReport).toHaveBeenLastCalledWith(params);
    expect(reportService.getTopUsers).toHaveBeenLastCalledWith(params);
    expect(reportService.getParkingSpotUsage).toHaveBeenLastCalledWith(params);
    expect(userService.listAdminUsers).toHaveBeenLastCalledWith({ limit: 1000 });
    expect(parkingSpotService.listAdminParkingSpots).toHaveBeenLastCalledWith({ limit: 1000 });
  });

  it("downloads CSV using the active filters", async () => {
    const wrapper = mountReports();
    await flushPromises();
    await wrapper.get('input[name="report-date-from"]').setValue("2026-06-01");

    const exportButton = wrapper.findAll("button").find((button) => button.text() === "Export reservations");
    await exportButton.trigger("click");
    await flushPromises();

    expect(reportService.downloadReportCsv).toHaveBeenCalledWith("reservations", {
      date_from: "2026-06-01",
    });
  });

  it("keeps intentional empty states for all compact report sections", async () => {
    reportService.getTopUsers.mockResolvedValue([]);
    reportService.getParkingSpotUsage.mockResolvedValue([]);
    reportService.getSummaryReport.mockResolvedValue({ ...summary, audit_trigger_summary: [] });

    const wrapper = mountReports();
    await flushPromises();

    expect(wrapper.text()).toContain("No reservation data yet");
    expect(wrapper.text()).toContain("No parking spot usage yet");
    expect(wrapper.text()).toContain("No audit trigger data yet");
    expect(wrapper.findAll(".report-compact-list")).toHaveLength(0);
    expect(wrapper.find(".report-trigger-list").exists()).toBe(false);
    expect(wrapper.findAll("button").some((button) => button.text() === "Export reservations")).toBe(true);
  });

  it("falls back to a spot reference only when display data is unavailable", async () => {
    parkingSpotService.listAdminParkingSpots.mockResolvedValue([]);

    const wrapper = mountReports();
    await flushPromises();

    expect(wrapper.text()).toContain("Spot #9");
    expect(wrapper.text()).not.toContain("Parking spot reference");
  });
});
