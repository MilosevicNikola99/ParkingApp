import apiClient from "./apiClient";

export async function listMyActiveParkingSpots(params = {}) {
  const response = await apiClient.get("/parking-spots/mine", { params });
  return response.data;
}