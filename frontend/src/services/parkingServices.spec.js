import { beforeEach, describe, expect, it, vi } from "vitest";

const apiClient = vi.hoisted(() => ({
  get: vi.fn(),
  patch: vi.fn(),
  post: vi.fn(),
}));

vi.mock("./apiClient", () => ({ default: apiClient }));

import {
  applyForAvailability,
  cancelApplication,
  getApplication,
  listMyApplications,
} from "./applicationService";
import {
  cancelAvailability,
  createAvailability,
  listMyAvailabilities,
  listOpenAvailabilities,
} from "./availabilityService";
import {
  cancelReservation,
  getReservation,
  listMyReservations,
} from "./reservationService";
import { listMyActiveParkingSpots } from "./parkingSpotService";

describe("parking API services", () => {
  beforeEach(() => {
    apiClient.get.mockResolvedValue({ data: [] });
    apiClient.patch.mockResolvedValue({ data: { id: 1 } });
    apiClient.post.mockResolvedValue({ data: { id: 1 } });
  });

  it("calls availability endpoints with expected requests", async () => {
    const payload = { parking_spot_id: 2 };

    await listOpenAvailabilities({ owner_id: 3 });
    await listMyAvailabilities();
    await createAvailability(payload);
    await cancelAvailability(4);

    expect(apiClient.get).toHaveBeenNthCalledWith(1, "/parking-availabilities", {
      params: { owner_id: 3 },
    });
    expect(apiClient.get).toHaveBeenNthCalledWith(2, "/parking-availabilities/my", { params: {} });
    expect(apiClient.post).toHaveBeenCalledWith("/parking-availabilities", payload);
    expect(apiClient.patch).toHaveBeenCalledWith("/parking-availabilities/4/cancel");
  });

  it("lists only parking spots owned by the current user", async () => {
    await listMyActiveParkingSpots();

    expect(apiClient.get).toHaveBeenCalledWith("/parking-spots/mine", { params: {} });
  });

  it("calls application endpoints with expected requests", async () => {
    await applyForAvailability(7, "Near entrance");
    await listMyApplications({ status: "pending" });
    await getApplication(8);
    await cancelApplication(8);

    expect(apiClient.post).toHaveBeenCalledWith("/parking-applications", {
      availability_id: 7,
      note: "Near entrance",
    });
    expect(apiClient.get).toHaveBeenNthCalledWith(1, "/parking-applications/my", {
      params: { status: "pending" },
    });
    expect(apiClient.get).toHaveBeenNthCalledWith(2, "/parking-applications/8");
    expect(apiClient.patch).toHaveBeenCalledWith("/parking-applications/8/cancel");
  });

  it("normalizes optional reservation cancellation reasons", async () => {
    await listMyReservations({ status: "active" });
    await getReservation(9);
    await cancelReservation(9, "  Changed plans  ");
    await cancelReservation(10, "   ");

    expect(apiClient.get).toHaveBeenNthCalledWith(1, "/parking-reservations/my", {
      params: { status: "active" },
    });
    expect(apiClient.get).toHaveBeenNthCalledWith(2, "/parking-reservations/9");
    expect(apiClient.patch).toHaveBeenNthCalledWith(1, "/parking-reservations/9/cancel", {
      reason: "Changed plans",
    });
    expect(apiClient.patch).toHaveBeenNthCalledWith(
      2,
      "/parking-reservations/10/cancel",
      undefined,
    );
  });
});
