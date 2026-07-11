import apiClient from "./apiClient";

export async function listAdminAssignmentAuditLogs(params = {}) {
  const response = await apiClient.get("/admin/assignment-audit-logs", { params });
  return response.data;
}

export async function getAdminAssignmentAuditLog(auditLogId) {
  const response = await apiClient.get(`/admin/assignment-audit-logs/${auditLogId}`);
  return response.data;
}

export async function getAdminAssignmentAuditLogByReservation(reservationId) {
  const response = await apiClient.get(`/admin/assignment-audit-logs/by-reservation/${reservationId}`);
  return response.data;
}
