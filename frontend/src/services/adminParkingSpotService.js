import apiClient from "./apiClient";

export async function listAdminParkingSpots(params = {}) {
  const response = await apiClient.get("/admin/parking-spots", { params });
  return response.data;
}

export async function getAdminParkingSpot(parkingSpotId) {
  const response = await apiClient.get(`/admin/parking-spots/${parkingSpotId}`);
  return response.data;
}

export async function createAdminParkingSpot(payload) {
  const response = await apiClient.post("/admin/parking-spots", payload);
  return response.data;
}

export async function updateAdminParkingSpot(parkingSpotId, payload) {
  const response = await apiClient.patch(`/admin/parking-spots/${parkingSpotId}`, payload);
  return response.data;
}

export async function deleteAdminParkingSpot(parkingSpotId) {
  await apiClient.delete(`/admin/parking-spots/${parkingSpotId}`);
}
