import apiClient from "./apiClient";

export async function applyForAvailability(availabilityId, note = null) {
  const response = await apiClient.post("/parking-applications", {
    availability_id: availabilityId,
    note,
  });
  return response.data;
}

export async function listMyApplications(params = {}) {
  const response = await apiClient.get("/parking-applications/my", { params });
  return response.data;
}

export async function getApplication(applicationId) {
  const response = await apiClient.get(`/parking-applications/${applicationId}`);
  return response.data;
}

export async function cancelApplication(applicationId) {
  const response = await apiClient.patch(`/parking-applications/${applicationId}/cancel`);
  return response.data;
}
