import apiClient from "./apiClient";

export async function listMyReservations(params = {}) {
  const response = await apiClient.get("/parking-reservations/my", { params });
  return response.data;
}

export async function getReservation(reservationId) {
  const response = await apiClient.get(`/parking-reservations/${reservationId}`);
  return response.data;
}

export async function cancelReservation(reservationId, reason = null) {
  const normalizedReason = reason?.trim() || null;
  const response = await apiClient.patch(
    `/parking-reservations/${reservationId}/cancel`,
    normalizedReason ? { reason: normalizedReason } : undefined,
  );
  return response.data;
}
