import apiClient from "./apiClient";

export async function listAdminReservations(params = {}) {
  const response = await apiClient.get("/admin/parking-reservations", { params });
  return response.data;
}

export async function listAdminReservationHistory(params = {}) {
  const response = await apiClient.get("/admin/parking-reservations/history", { params });
  return response.data;
}
