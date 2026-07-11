import apiClient from "./apiClient";

export async function listAdminParkingApplications(params = {}) {
  const response = await apiClient.get("/admin/parking-applications", { params });
  return response.data;
}
