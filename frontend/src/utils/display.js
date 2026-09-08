const statusLabels = {
  active: "Active",
  assigned: "Assigned",
  cancelled: "Cancelled",
  completed: "Completed",
  current_active: "Current",
  expired: "Expired",
  historical: "Past",
  inactive: "Inactive",
  open: "Open for requests",
  pending: "Waiting for assignment",
  rejected: "Not selected",
  selected: "Selected",
  admin_override: "Admin override",
  manual_admin: "Manual admin",
  manual_owner: "Manual owner",
  scheduled: "Scheduled",
  system: "Automatic",
};

export function getStatusLabel(status) {
  if (!status) return "Unknown";
  if (statusLabels[status]) return statusLabels[status];
  const label = status.replaceAll("_", " ");
  return label.charAt(0).toUpperCase() + label.slice(1);
}

export function getParkingSpotLabel(spot, fallbackId) {
  if (spot?.code) {
    return spot.location ? `${spot.code} - ${spot.location}` : spot.code;
  }
  return fallbackId ? `Parking spot #${fallbackId}` : "Parking spot";
}
