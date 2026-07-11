"""Pydantic request and response schemas."""

from app.schemas.admin_report import (
    AdminSummaryReport,
    ApplicationSummaryReport,
    AuditTriggerSummaryItem,
    AvailabilitySummaryReport,
    ParkingSpotUsageReportItem,
    ReservationSummaryReport,
    TopReservedUserReportItem,
)
from app.schemas.auth import LoginRequest, Token, TokenPayload
from app.schemas.parking_assignment_audit_log import ParkingAssignmentAuditLogCreate, ParkingAssignmentAuditLogRead
from app.schemas.parking_availability import (
    ParkingAvailabilityBase,
    ParkingAvailabilityCreate,
    ParkingAvailabilityRead,
    ParkingAvailabilityUpdate,
)
from app.schemas.parking_application import (
    ParkingApplicationBase,
    ParkingApplicationCreate,
    ParkingApplicationRead,
    ParkingApplicationUpdate,
)
from app.schemas.parking_reservation import (
    AdminReservationCancellationRequest,
    AdminReservationOverrideRequest,
    ParkingReservationBase,
    ParkingReservationCreate,
    ParkingReservationHistoryRead,
    ParkingReservationHistoryState,
    ParkingReservationRead,
    ParkingReservationUpdate,
    ParkingReassignmentRequest,
    ReservationCancellationRequest,
)
from app.schemas.parking_spot import ParkingSpotBase, ParkingSpotCreate, ParkingSpotRead, ParkingSpotUpdate
from app.schemas.team import TeamBase, TeamCreate, TeamRead, TeamUpdate
from app.schemas.user import UserBase, UserCreate, UserRead, UserUpdate

__all__ = [
    "AdminReservationCancellationRequest",
    "AdminReservationOverrideRequest",
    "AdminSummaryReport",
    "ApplicationSummaryReport",
    "AuditTriggerSummaryItem",
    "AvailabilitySummaryReport",
    "LoginRequest",
    "ParkingAssignmentAuditLogCreate",
    "ParkingAssignmentAuditLogRead",
    "ParkingAvailabilityBase",
    "ParkingAvailabilityCreate",
    "ParkingAvailabilityRead",
    "ParkingAvailabilityUpdate",
    "ParkingApplicationBase",
    "ParkingApplicationCreate",
    "ParkingApplicationRead",
    "ParkingApplicationUpdate",
    "ParkingReservationBase",
    "ParkingReservationCreate",
    "ParkingReservationHistoryRead",
    "ParkingReservationHistoryState",
    "ParkingReservationRead",
    "ParkingReservationUpdate",
    "ParkingReassignmentRequest",
    "ReservationCancellationRequest",
    "ParkingSpotBase",
    "ParkingSpotCreate",
    "ParkingSpotRead",
    "ParkingSpotUpdate",
    "ParkingSpotUsageReportItem",
    "ReservationSummaryReport",
    "TeamBase",
    "TeamCreate",
    "TeamRead",
    "TeamUpdate",
    "Token",
    "TokenPayload",
    "TopReservedUserReportItem",
    "UserBase",
    "UserCreate",
    "UserRead",
    "UserUpdate",
]
