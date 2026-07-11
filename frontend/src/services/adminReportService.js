import apiClient from "./apiClient";

export async function getSummaryReport(params = {}) {
  const response = await apiClient.get("/admin/reports/summary", { params });
  return response.data;
}

export async function getTopUsers(params = {}) {
  const response = await apiClient.get("/admin/reports/top-users", { params });
  return response.data;
}

export async function getParkingSpotUsage(params = {}) {
  const response = await apiClient.get("/admin/reports/parking-spot-usage", { params });
  return response.data;
}

export async function downloadReportCsv(reportName, params = {}) {
  const response = await apiClient.get(`/admin/reports/${reportName}.csv`, {
    params,
    responseType: "blob",
  });
  const filename = response.headers?.["content-disposition"]?.match(/filename="?([^"]+)"?/)?.[1]
    || `${reportName}.csv`;
  const objectUrl = window.URL.createObjectURL(response.data);
  const downloadLink = document.createElement("a");
  downloadLink.href = objectUrl;
  downloadLink.download = filename;
  downloadLink.click();
  window.URL.revokeObjectURL(objectUrl);
}
