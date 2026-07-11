import { beforeEach, describe, expect, it, vi } from "vitest";

const apiClient = vi.hoisted(() => ({
  delete: vi.fn(),
  get: vi.fn(),
  patch: vi.fn(),
  post: vi.fn(),
}));

vi.mock("./apiClient", () => ({ default: apiClient }));

import {
  createAdminParkingSpot,
  deleteAdminParkingSpot,
  listAdminParkingSpots,
  updateAdminParkingSpot,
} from "./adminParkingSpotService";
import {
  createAdminTeam,
  deleteAdminTeam,
  listAdminTeams,
  updateAdminTeam,
} from "./adminTeamService";
import {
  createAdminUser,
  deleteAdminUser,
  listAdminUsers,
  updateAdminUser,
} from "./adminUserService";

describe("admin API services", () => {
  beforeEach(() => {
    apiClient.delete.mockResolvedValue({});
    apiClient.get.mockResolvedValue({ data: [] });
    apiClient.patch.mockResolvedValue({ data: { id: 1 } });
    apiClient.post.mockResolvedValue({ data: { id: 1 } });
  });

  it("calls team management endpoints", async () => {
    const payload = { name: "Operations" };
    await listAdminTeams({ limit: 50 });
    await createAdminTeam(payload);
    await updateAdminTeam(3, payload);
    await deleteAdminTeam(3);

    expect(apiClient.get).toHaveBeenCalledWith("/admin/teams", { params: { limit: 50 } });
    expect(apiClient.post).toHaveBeenCalledWith("/admin/teams", payload);
    expect(apiClient.patch).toHaveBeenCalledWith("/admin/teams/3", payload);
    expect(apiClient.delete).toHaveBeenCalledWith("/admin/teams/3");
  });

  it("calls user management endpoints without transforming sensitive fields", async () => {
    const payload = { username: "new.user", password: "not-a-real-password" };
    await listAdminUsers({ team_id: 4 });
    await createAdminUser(payload);
    await updateAdminUser(5, { is_active: false });
    await deleteAdminUser(5);

    expect(apiClient.get).toHaveBeenCalledWith("/admin/users", { params: { team_id: 4 } });
    expect(apiClient.post).toHaveBeenCalledWith("/admin/users", payload);
    expect(apiClient.patch).toHaveBeenCalledWith("/admin/users/5", { is_active: false });
    expect(apiClient.delete).toHaveBeenCalledWith("/admin/users/5");
  });

  it("calls parking spot management endpoints", async () => {
    const payload = { code: "A-12", owner_id: null };
    await listAdminParkingSpots({ is_active: true });
    await createAdminParkingSpot(payload);
    await updateAdminParkingSpot(6, payload);
    await deleteAdminParkingSpot(6);

    expect(apiClient.get).toHaveBeenCalledWith("/admin/parking-spots", { params: { is_active: true } });
    expect(apiClient.post).toHaveBeenCalledWith("/admin/parking-spots", payload);
    expect(apiClient.patch).toHaveBeenCalledWith("/admin/parking-spots/6", payload);
    expect(apiClient.delete).toHaveBeenCalledWith("/admin/parking-spots/6");
  });
});
