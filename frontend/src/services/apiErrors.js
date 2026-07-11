const DETAIL_MESSAGES = {
  "Not enough permissions": "You do not have permission to perform this action.",
  "Admins cannot delete their own account": "You cannot delete your own administrator account.",
  "Email already exists": "A user with this email already exists.",
  "Owner is inactive": "Only an active user can own a parking spot.",
  "Owner not found": "The selected parking spot owner could not be found.",
  "Override reason is required": "Enter a reason for the reservation override.",
  "Active parking reservation not found": "No active reservation exists for this availability.",
  "Parking applicant is already reserved": "The selected applicant already has the active reservation.",
  "Parking applicant is inactive": "The selected applicant is inactive.",
  "Parking applicant not found": "The selected applicant could not be found.",
  "Parking application does not belong to availability": "The selected application does not belong to this availability.",
  "Parking application is already reserved": "The selected application already has a reservation.",
  "Parking application is not pending": "Only a pending application can be selected.",
  "Parking availability is not assigned": "This availability does not have an active assignment to replace.",
  "Parking spot cannot be deleted": "This parking spot cannot be deleted because it is in use.",
  "Parking spot code already exists": "A parking spot with this code already exists.",
  "Parking application already exists": "You already applied for this availability.",
  "Parking application cannot be cancelled": "Only pending applications can be cancelled.",
  "Parking application not found": "The parking application could not be found.",
  "Parking availability not found": "The parking availability could not be found.",
  "Parking availability is not open": "This parking availability is no longer open.",
  "Parking availability has expired": "This parking availability has expired.",
  "Parking availability overlaps with an existing availability":
    "This time range overlaps another availability for the parking spot.",
  "Parking availability cannot be cancelled": "Only open availabilities can be cancelled.",
  "Parking spot is inactive": "This parking spot is inactive.",
  "Parking spot not found": "The parking spot could not be found.",
  "Parking reservation not found": "The parking reservation could not be found.",
  "Parking reservation is not active": "Only active reservations can be cancelled.",
  "Parking reservation cancellation conflict": "The reservation could not be cancelled.",
  "Parking reservation already exists": "This availability already has a reservation.",
  "Parking reservation override conflict": "The reservation override could not be completed.",
  "Parking reservation override is invalid": "The reservation override request is invalid.",
  "Team cannot be deleted": "This team cannot be deleted because it is in use.",
  "Team name already exists": "A team with this name already exists.",
  "Team not found": "The selected team could not be found.",
  "User cannot be deleted": "This user cannot be deleted because the account is in use.",
  "User email or username already exists": "A user with this email or username already exists.",
  "User not found": "The user could not be found.",
  "Username already exists": "A user with this username already exists.",
};

export function getApiErrorMessage(error, fallbackMessage) {
  const status = error?.response?.status;
  const detail = error?.response?.data?.detail;

  if (status === 401) {
    return "Your session has expired. Sign in again.";
  }
  if (typeof detail === "string" && DETAIL_MESSAGES[detail]) {
    return DETAIL_MESSAGES[detail];
  }
  if (status === 403) {
    return "You do not have permission to perform this action.";
  }
  if (status === 404) {
    return "The requested parking record could not be found.";
  }
  if (status === 409) {
    return "The parking record changed and the action could not be completed.";
  }
  if (status === 422) {
    return "Check the entered values and try again.";
  }

  return fallbackMessage;
}
