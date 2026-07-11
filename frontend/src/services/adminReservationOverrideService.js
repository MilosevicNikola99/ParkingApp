import apiClient from "./apiClient";

export async function manualOverrideAssignment(availabilityId, applicationId, reason) {
  const response = await apiClient.post(
    `/admin/parking-availabilities/${availabilityId}/override-assign`,
    {
      application_id: applicationId,
      reason: reason.trim(),
    },
  );
  return response.data;
}

export async function replaceReservationAssignment(availabilityId, selector, reason) {
  const payload = { reason: reason.trim() };
  if (typeof selector === "object" && selector !== null) {
    if (selector.applicationId !== undefined) {
      payload.application_id = selector.applicationId;
    }
    if (selector.applicantId !== undefined) {
      payload.applicant_id = selector.applicantId;
    }
  } else {
    payload.application_id = selector;
  }

  const response = await apiClient.post(
    `/admin/parking-availabilities/${availabilityId}/replace-reservation`,
    payload,
  );
  return response.data;
}
