from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.config import Settings, get_settings
from app.models.parking_application import ParkingApplication
from app.models.parking_availability import ParkingAvailability

RecentWinCountProvider = Callable[[Sequence[int], datetime], Mapping[int, int]]
RankingOrderValues = tuple[int, int, int, datetime, int]


@dataclass(frozen=True)
class ParkingApplicationRankingAuditDetail:
    application_id: int
    applicant_id: int
    applicant_team_id: int | None
    owner_team_id: int | None
    is_same_team_as_owner: bool
    team_priority_active: bool
    recent_win_count: int
    is_over_soft_limit: bool
    application_created_at: datetime
    ranking_order_values: RankingOrderValues
    final_rank_position: int
    selected: bool


@dataclass(frozen=True)
class ParkingApplicationRankingResult:
    selected_application: ParkingApplication
    ranked_applications: tuple[ParkingApplication, ...]
    audit_details: tuple[ParkingApplicationRankingAuditDetail, ...]


class ParkingApplicationRankingService:
    """Rank pending applications for a parking availability.

    Same-team priority applies only while the availability priority window is
    active. Within each eligibility group, applicants below the soft recent-win
    limit rank first. Recent win count and deterministic first-applied ordering
    then break ties without blocking any applicant from assignment.
    """

    def __init__(
        self,
        now_provider: Callable[[], datetime] | None = None,
        recent_win_count_provider: RecentWinCountProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.now_provider = now_provider or (lambda: datetime.now(UTC))
        self.recent_win_count_provider = recent_win_count_provider
        self.settings = settings or get_settings()

    def select_winning_application(
        self,
        availability: ParkingAvailability,
        applications: Sequence[ParkingApplication],
    ) -> ParkingApplication:
        return self.rank_applications_with_audit(availability, applications).selected_application

    def rank_applications_for_availability(
        self,
        availability: ParkingAvailability,
        applications: Sequence[ParkingApplication],
    ) -> list[ParkingApplication]:
        if not applications:
            return []

        return list(self.rank_applications_with_audit(availability, applications).ranked_applications)

    def rank_applications_with_audit(
        self,
        availability: ParkingAvailability,
        applications: Sequence[ParkingApplication],
    ) -> ParkingApplicationRankingResult:
        if not applications:
            raise ValueError("Cannot rank an empty application list")

        now = self._now()
        same_team_priority_active = self._same_team_priority_is_active(availability, now)
        owner_team_id = availability.owner.team_id if availability.owner is not None else None
        recent_win_counts = self._recent_win_counts(applications, now)
        candidates = [
            (
                application,
                self._ranking_key(
                    application,
                    owner_team_id=owner_team_id,
                    same_team_priority_active=same_team_priority_active,
                    recent_win_count=recent_win_counts.get(application.applicant_id, 0),
                ),
            )
            for application in applications
        ]
        candidates.sort(key=lambda candidate: candidate[1])
        ranked_applications = tuple(application for application, _ranking_values in candidates)
        audit_details = tuple(
            self._audit_detail(
                application,
                ranking_values=ranking_values,
                final_rank_position=position,
                owner_team_id=owner_team_id,
                team_priority_active=same_team_priority_active,
                recent_win_count=recent_win_counts.get(application.applicant_id, 0),
            )
            for position, (application, ranking_values) in enumerate(candidates, start=1)
        )
        return ParkingApplicationRankingResult(
            selected_application=ranked_applications[0],
            ranked_applications=ranked_applications,
            audit_details=audit_details,
        )

    def _audit_detail(
        self,
        application: ParkingApplication,
        *,
        ranking_values: RankingOrderValues,
        final_rank_position: int,
        owner_team_id: int | None,
        team_priority_active: bool,
        recent_win_count: int,
    ) -> ParkingApplicationRankingAuditDetail:
        applicant_team_id = application.applicant.team_id if application.applicant is not None else None
        is_same_team_as_owner = owner_team_id is not None and applicant_team_id == owner_team_id
        return ParkingApplicationRankingAuditDetail(
            application_id=application.id,
            applicant_id=application.applicant_id,
            applicant_team_id=applicant_team_id,
            owner_team_id=owner_team_id,
            is_same_team_as_owner=is_same_team_as_owner,
            team_priority_active=team_priority_active,
            recent_win_count=recent_win_count,
            is_over_soft_limit=self._soft_limit_rank(recent_win_count) == 1,
            application_created_at=self._as_aware_utc(application.created_at),
            ranking_order_values=ranking_values,
            final_rank_position=final_rank_position,
            selected=final_rank_position == 1,
        )

    def _ranking_key(
        self,
        application: ParkingApplication,
        *,
        owner_team_id: int | None,
        same_team_priority_active: bool,
        recent_win_count: int,
    ) -> RankingOrderValues:
        same_team_priority_rank = 1
        if same_team_priority_active and owner_team_id is not None:
            applicant_team_id = application.applicant.team_id if application.applicant is not None else None
            if applicant_team_id == owner_team_id:
                same_team_priority_rank = 0

        return (
            same_team_priority_rank,
            self._soft_limit_rank(recent_win_count),
            recent_win_count,
            self._as_aware_utc(application.created_at),
            application.id or 0,
        )

    def _soft_limit_rank(self, recent_win_count: int) -> int:
        return int(recent_win_count >= self.settings.recent_win_soft_limit)

    def _recent_win_counts(
        self,
        applications: Sequence[ParkingApplication],
        now: datetime,
    ) -> Mapping[int, int]:
        if self.recent_win_count_provider is None:
            return {}

        applicant_ids = list(dict.fromkeys(application.applicant_id for application in applications))
        since = now - timedelta(days=self.settings.recent_win_fairness_window_days)
        return self.recent_win_count_provider(applicant_ids, since)

    def _same_team_priority_is_active(self, availability: ParkingAvailability, now: datetime) -> bool:
        if availability.priority_until is None:
            return False

        return now <= self._as_aware_utc(availability.priority_until)

    def _now(self) -> datetime:
        return self._as_aware_utc(self.now_provider())

    def _as_aware_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=UTC)

        return value.astimezone(UTC)
