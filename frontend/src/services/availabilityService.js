import apiClient from "./apiClient";

export async function listOpenAvailabilities(params = {}) {
  const response = await apiClient.get("/parking-availabilities", { params });
  return response.data;
}

export async function listMyAvailabilities(params = {}) {
  const response = await apiClient.get("/parking-availabilities/my", { params });
  return response.data;
}

export async function createAvailability(payload) {
  const response = await apiClient.post("/parking-availabilities", payload);
  return response.data;
}

export async function cancelAvailability(availabilityId) {
  const response = await apiClient.patch(`/parking-availabilities/${availabilityId}/cancel`);
  return response.data;
}
