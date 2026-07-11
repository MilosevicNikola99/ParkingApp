import { beforeEach, describe, expect, it, vi } from "vitest";

const apiClient = vi.hoisted(() => ({
  get: vi.fn(),
}));

vi.mock("./apiClient", () => ({ default: apiClient }));

import {
  downloadReportCsv,
  getParkingSpotUsage,
  getSummaryReport,
  getTopUsers,
} from "./adminReportService";

describe("admin report API service", () => {
  beforeEach(() => {
    apiClient.get.mockResolvedValue({ data: [] });
  });

  it("calls report endpoints with date filters", async () => {
    const params = { date_from: "2026-06-01", date_to: "2026-06-30" };

    await getSummaryReport(params);
    await getTopUsers(params);
    await getParkingSpotUsage(params);

    expect(apiClient.get).toHaveBeenNthCalledWith(1, "/admin/reports/summary", { params });
    expect(apiClient.get).toHaveBeenNthCalledWith(2, "/admin/reports/top-users", { params });
    expect(apiClient.get).toHaveBeenNthCalledWith(3, "/admin/reports/parking-spot-usage", { params });
  });

  it("downloads CSV through the authenticated API client", async () => {
    const click = vi.fn();
    vi.spyOn(document, "createElement").mockReturnValue({ click });
    window.URL.createObjectURL = vi.fn(() => "blob:report");
    window.URL.revokeObjectURL = vi.fn();
    apiClient.get.mockResolvedValue({
      data: new Blob(["id,status\n1,active\n"], { type: "text/csv" }),
      headers: { "content-disposition": 'attachment; filename="parking-reservations.csv"' },
    });

    await downloadReportCsv("reservations", { date_from: "2026-06-01" });

    expect(apiClient.get).toHaveBeenCalledWith("/admin/reports/reservations.csv", {
      params: { date_from: "2026-06-01" },
      responseType: "blob",
    });
    expect(click).toHaveBeenCalledOnce();
    expect(window.URL.revokeObjectURL).toHaveBeenCalledWith("blob:report");
  });
});
