import apiClient from "./apiClient";

export async function listAdminTeams(params = {}) {
  const response = await apiClient.get("/admin/teams", { params });
  return response.data;
}

export async function getAdminTeam(teamId) {
  const response = await apiClient.get(`/admin/teams/${teamId}`);
  return response.data;
}

export async function createAdminTeam(payload) {
  const response = await apiClient.post("/admin/teams", payload);
  return response.data;
}

export async function updateAdminTeam(teamId, payload) {
  const response = await apiClient.patch(`/admin/teams/${teamId}`, payload);
  return response.data;
}

export async function deleteAdminTeam(teamId) {
  await apiClient.delete(`/admin/teams/${teamId}`);
}
