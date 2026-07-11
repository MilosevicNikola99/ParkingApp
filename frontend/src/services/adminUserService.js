import apiClient from "./apiClient";

export async function listAdminUsers(params = {}) {
  const response = await apiClient.get("/admin/users", { params });
  return response.data;
}

export async function getAdminUser(userId) {
  const response = await apiClient.get(`/admin/users/${userId}`);
  return response.data;
}

export async function createAdminUser(payload) {
  const response = await apiClient.post("/admin/users", payload);
  return response.data;
}

export async function updateAdminUser(userId, payload) {
  const response = await apiClient.patch(`/admin/users/${userId}`, payload);
  return response.data;
}

export async function deleteAdminUser(userId) {
  await apiClient.delete(`/admin/users/${userId}`);
}
