from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.core.config import Settings
from app.db.base import Base
from app.models.parking_application import ParkingApplication, ParkingApplicationStatus
from app.models.parking_availability import ParkingAvailability
from app.models.parking_spot import ParkingSpot
from app.models.team import Team
from app.models.user import User, UserRole
from app.repositories.parking_applications import ParkingApplicationRepository
from app.repositories.parking_availabilities import ParkingAvailabilityRepository
from app.repositories.parking_spots import ParkingSpotRepository
from app.repositories.teams import TeamRepository
from app.repositories.users import UserRepository
from app.services.parking_application_ranking import ParkingApplicationRankingService

TEST_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()


def create_team(db_session: Session, suffix: str) -> Team:
    return TeamRepository(db_session).create(name=f"Team {suffix}")


def create_user(
    db_session: Session,
    *,
    suffix: str,
    role: UserRole = UserRole.EMPLOYEE,
    team_id: int | None = None,
) -> User:
    return UserRepository(db_session).create(
        email=f"ranking.{suffix}@example.com",
        username=f"ranking{suffix}",
        first_name="Ranking",
        last_name="User",
        hashed_password="hashed-password",
        role=role,
        team_id=team_id,
    )


def create_parking_spot(db_session: Session, *, suffix: str, owner_id: int) -> ParkingSpot:
    return ParkingSpotRepository(db_session).create(code=f"RK-{suffix}", owner_id=owner_id)


def create_availability(
    db_session: Session,
    *,
    suffix: str,
    owner_id: int,
    priority_until: datetime | None,
) -> ParkingAvailability:
    parking_spot = create_parking_spot(db_session, suffix=suffix, owner_id=owner_id)
    availability = ParkingAvailabilityRepository(db_session).create(
        parking_spot_id=parking_spot.id,
        owner_id=owner_id,
        start_at=TEST_NOW + timedelta(hours=1),
        end_at=TEST_NOW + timedelta(hours=5),
        priority_until=priority_until,
    )
    return ParkingAvailabilityRepository(db_session).get_by_id(availability.id)


def create_application(
    db_session: Session,
    *,
    availability_id: int,
    applicant_id: int,
    created_at: datetime,
    status: ParkingApplicationStatus = ParkingApplicationStatus.PENDING,
) -> ParkingApplication:
    application = ParkingApplicationRepository(db_session).create(
        availability_id=availability_id,
        applicant_id=applicant_id,
        status=status,
    )
    application.created_at = created_at
    application.updated_at = created_at
    db_session.flush()
    db_session.refresh(application)
    return application


def ranking_service(
    now: datetime = TEST_NOW,
    recent_win_counts: dict[int, int] | None = None,
    fairness_window_days: int = 30,
    soft_limit: int = 2,
) -> ParkingApplicationRankingService:
    count_provider = None
    if recent_win_counts is not None:
        count_provider = lambda user_ids, since: {
            user_id: recent_win_counts[user_id] for user_id in user_ids if user_id in recent_win_counts
        }

    return ParkingApplicationRankingService(
        now_provider=lambda: now,
        recent_win_count_provider=count_provider,
        settings=Settings(
            recent_win_fairness_window_days=fairness_window_days,
            recent_win_soft_limit=soft_limit,
        ),
    )


def pending_applications(db_session: Session, availability_id: int) -> list[ParkingApplication]:
    return ParkingApplicationRepository(db_session).list_pending_by_availability_id(availability_id)


def create_rankable_pair(
    db_session: Session,
    *,
    suffix: str,
    priority_until: datetime | None = None,
) -> tuple[ParkingAvailability, User, User, ParkingApplication, ParkingApplication]:
    owner = create_user(db_session, suffix=f"{suffix}owner", role=UserRole.PARKING_OWNER)
    first_applicant = create_user(db_session, suffix=f"{suffix}first")
    second_applicant = create_user(db_session, suffix=f"{suffix}second")
    availability = create_availability(
        db_session,
        suffix=suffix,
        owner_id=owner.id,
        priority_until=priority_until,
    )
    first_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=first_applicant.id,
        created_at=TEST_NOW - timedelta(hours=2),
    )
    second_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=second_applicant.id,
        created_at=TEST_NOW - timedelta(hours=1),
    )
    return availability, first_applicant, second_applicant, first_application, second_application


def test_before_priority_until_same_team_applicant_beats_earlier_non_team_applicant(
    db_session: Session,
) -> None:
    owner_team = create_team(db_session, "same-team-priority-owner")
    other_team = create_team(db_session, "same-team-priority-other")
    owner = create_user(db_session, suffix="sameowner", role=UserRole.PARKING_OWNER, team_id=owner_team.id)
    same_team_applicant = create_user(db_session, suffix="sameapplicant", team_id=owner_team.id)
    non_team_applicant = create_user(db_session, suffix="nonteamapplicant", team_id=other_team.id)
    availability = create_availability(
        db_session,
        suffix="samepriority",
        owner_id=owner.id,
        priority_until=TEST_NOW + timedelta(hours=1),
    )
    earlier_non_team = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=non_team_applicant.id,
        created_at=TEST_NOW - timedelta(hours=2),
    )
    later_same_team = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=same_team_applicant.id,
        created_at=TEST_NOW - timedelta(hours=1),
    )

    winner = ranking_service(
        recent_win_counts={
            same_team_applicant.id: 5,
            non_team_applicant.id: 0,
        },
    ).select_winning_application(availability, pending_applications(db_session, availability.id))

    assert winner.id == later_same_team.id
    assert winner.id != earlier_non_team.id


def test_at_priority_until_same_team_priority_is_still_active(db_session: Session) -> None:
    owner_team = create_team(db_session, "at-window-owner")
    other_team = create_team(db_session, "at-window-other")
    owner = create_user(db_session, suffix="atwindowowner", role=UserRole.PARKING_OWNER, team_id=owner_team.id)
    same_team_applicant = create_user(db_session, suffix="atwindowsame", team_id=owner_team.id)
    non_team_applicant = create_user(db_session, suffix="atwindownonteam", team_id=other_team.id)
    availability = create_availability(
        db_session,
        suffix="atwindow",
        owner_id=owner.id,
        priority_until=TEST_NOW,
    )
    earlier_non_team = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=non_team_applicant.id,
        created_at=TEST_NOW - timedelta(hours=2),
    )
    later_same_team = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=same_team_applicant.id,
        created_at=TEST_NOW - timedelta(hours=1),
    )

    winner = ranking_service(now=TEST_NOW).select_winning_application(
        availability,
        pending_applications(db_session, availability.id),
    )

    assert winner.id == later_same_team.id
    assert winner.id != earlier_non_team.id


def test_before_priority_until_oldest_same_team_applicant_wins_among_same_team_applicants(
    db_session: Session,
) -> None:
    owner_team = create_team(db_session, "oldest-same-owner")
    other_team = create_team(db_session, "oldest-same-other")
    owner = create_user(db_session, suffix="oldestsameowner", role=UserRole.PARKING_OWNER, team_id=owner_team.id)
    older_same_team_applicant = create_user(db_session, suffix="oldersame", team_id=owner_team.id)
    newer_same_team_applicant = create_user(db_session, suffix="newersame", team_id=owner_team.id)
    non_team_applicant = create_user(db_session, suffix="oldestsamenonteam", team_id=other_team.id)
    availability = create_availability(
        db_session,
        suffix="oldestsame",
        owner_id=owner.id,
        priority_until=TEST_NOW + timedelta(minutes=30),
    )
    create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=non_team_applicant.id,
        created_at=TEST_NOW - timedelta(hours=3),
    )
    older_same_team = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=older_same_team_applicant.id,
        created_at=TEST_NOW - timedelta(hours=2),
    )
    newer_same_team = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=newer_same_team_applicant.id,
        created_at=TEST_NOW - timedelta(hours=1),
    )

    ranked = ranking_service().rank_applications_for_availability(
        availability,
        pending_applications(db_session, availability.id),
    )

    assert [application.id for application in ranked[:2]] == [older_same_team.id, newer_same_team.id]


def test_before_priority_until_fewer_recent_wins_wins_among_same_team_applicants(
    db_session: Session,
) -> None:
    owner_team = create_team(db_session, "fair-same-owner")
    owner = create_user(db_session, suffix="fairsameowner", role=UserRole.PARKING_OWNER, team_id=owner_team.id)
    more_wins_applicant = create_user(db_session, suffix="fairsamemore", team_id=owner_team.id)
    fewer_wins_applicant = create_user(db_session, suffix="fairsamefewer", team_id=owner_team.id)
    availability = create_availability(
        db_session,
        suffix="fairsame",
        owner_id=owner.id,
        priority_until=TEST_NOW + timedelta(minutes=30),
    )
    earlier_more_wins = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=more_wins_applicant.id,
        created_at=TEST_NOW - timedelta(hours=2),
    )
    later_fewer_wins = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=fewer_wins_applicant.id,
        created_at=TEST_NOW - timedelta(hours=1),
    )

    winner = ranking_service(
        recent_win_counts={
            more_wins_applicant.id: 2,
            fewer_wins_applicant.id: 1,
        },
    ).select_winning_application(availability, pending_applications(db_session, availability.id))

    assert winner.id == later_fewer_wins.id
    assert winner.id != earlier_more_wins.id


def test_before_priority_until_without_same_team_applicants_oldest_pending_wins(
    db_session: Session,
) -> None:
    owner_team = create_team(db_session, "no-same-owner")
    other_team = create_team(db_session, "no-same-other")
    owner = create_user(db_session, suffix="nosameowner", role=UserRole.PARKING_OWNER, team_id=owner_team.id)
    older_applicant = create_user(db_session, suffix="nosameolder", team_id=other_team.id)
    newer_applicant = create_user(db_session, suffix="nosamenewer", team_id=other_team.id)
    availability = create_availability(
        db_session,
        suffix="nosame",
        owner_id=owner.id,
        priority_until=TEST_NOW + timedelta(minutes=30),
    )
    older_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=older_applicant.id,
        created_at=TEST_NOW - timedelta(hours=2),
    )
    create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=newer_applicant.id,
        created_at=TEST_NOW - timedelta(hours=1),
    )

    winner = ranking_service().select_winning_application(availability, pending_applications(db_session, availability.id))

    assert winner.id == older_application.id


def test_before_priority_until_fewer_recent_wins_wins_when_no_same_team_applicants(
    db_session: Session,
) -> None:
    owner_team = create_team(db_session, "fair-non-team-owner")
    other_team = create_team(db_session, "fair-non-team-other")
    owner = create_user(db_session, suffix="fairnonowner", role=UserRole.PARKING_OWNER, team_id=owner_team.id)
    more_wins_applicant = create_user(db_session, suffix="fairnonmore", team_id=other_team.id)
    fewer_wins_applicant = create_user(db_session, suffix="fairnonfewer", team_id=other_team.id)
    availability = create_availability(
        db_session,
        suffix="fairnon",
        owner_id=owner.id,
        priority_until=TEST_NOW + timedelta(minutes=30),
    )
    earlier_more_wins = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=more_wins_applicant.id,
        created_at=TEST_NOW - timedelta(hours=2),
    )
    later_fewer_wins = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=fewer_wins_applicant.id,
        created_at=TEST_NOW - timedelta(hours=1),
    )

    winner = ranking_service(
        recent_win_counts={
            more_wins_applicant.id: 3,
            fewer_wins_applicant.id: 0,
        },
    ).select_winning_application(availability, pending_applications(db_session, availability.id))

    assert winner.id == later_fewer_wins.id
    assert winner.id != earlier_more_wins.id


def test_after_priority_until_oldest_pending_wins_regardless_of_team(db_session: Session) -> None:
    owner_team = create_team(db_session, "after-owner")
    other_team = create_team(db_session, "after-other")
    owner = create_user(db_session, suffix="afterowner", role=UserRole.PARKING_OWNER, team_id=owner_team.id)
    same_team_applicant = create_user(db_session, suffix="aftersame", team_id=owner_team.id)
    non_team_applicant = create_user(db_session, suffix="afternonteam", team_id=other_team.id)
    availability = create_availability(
        db_session,
        suffix="after",
        owner_id=owner.id,
        priority_until=TEST_NOW - timedelta(minutes=1),
    )
    older_non_team = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=non_team_applicant.id,
        created_at=TEST_NOW - timedelta(hours=2),
    )
    create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=same_team_applicant.id,
        created_at=TEST_NOW - timedelta(hours=1),
    )

    winner = ranking_service().select_winning_application(availability, pending_applications(db_session, availability.id))

    assert winner.id == older_non_team.id


def test_after_priority_until_fewer_recent_wins_wins_regardless_of_team(db_session: Session) -> None:
    owner_team = create_team(db_session, "fair-after-owner")
    other_team = create_team(db_session, "fair-after-other")
    owner = create_user(db_session, suffix="fairafterowner", role=UserRole.PARKING_OWNER, team_id=owner_team.id)
    same_team_applicant = create_user(db_session, suffix="fairaftersame", team_id=owner_team.id)
    non_team_applicant = create_user(db_session, suffix="fairafternonteam", team_id=other_team.id)
    availability = create_availability(
        db_session,
        suffix="fairafter",
        owner_id=owner.id,
        priority_until=TEST_NOW - timedelta(minutes=1),
    )
    earlier_same_team = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=same_team_applicant.id,
        created_at=TEST_NOW - timedelta(hours=2),
    )
    later_non_team = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=non_team_applicant.id,
        created_at=TEST_NOW - timedelta(hours=1),
    )

    winner = ranking_service(
        recent_win_counts={
            same_team_applicant.id: 2,
            non_team_applicant.id: 0,
        },
    ).select_winning_application(availability, pending_applications(db_session, availability.id))

    assert winner.id == later_non_team.id
    assert winner.id != earlier_same_team.id


def test_equal_recent_wins_falls_back_to_oldest_created_at(db_session: Session) -> None:
    owner = create_user(db_session, suffix="fairfallbackowner", role=UserRole.PARKING_OWNER)
    older_applicant = create_user(db_session, suffix="fairfallbackolder")
    newer_applicant = create_user(db_session, suffix="fairfallbacknewer")
    availability = create_availability(
        db_session,
        suffix="fairfallback",
        owner_id=owner.id,
        priority_until=None,
    )
    older_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=older_applicant.id,
        created_at=TEST_NOW - timedelta(hours=2),
    )
    create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=newer_applicant.id,
        created_at=TEST_NOW - timedelta(hours=1),
    )

    winner = ranking_service(
        recent_win_counts={
            older_applicant.id: 1,
            newer_applicant.id: 1,
        },
    ).select_winning_application(availability, pending_applications(db_session, availability.id))

    assert winner.id == older_application.id


def test_applicant_below_soft_limit_ranks_before_applicant_at_soft_limit(db_session: Session) -> None:
    availability, at_limit_applicant, below_limit_applicant, at_limit_application, below_limit_application = (
        create_rankable_pair(db_session, suffix="softboundary")
    )

    winner = ranking_service(
        recent_win_counts={
            at_limit_applicant.id: 2,
            below_limit_applicant.id: 1,
        },
    ).select_winning_application(availability, pending_applications(db_session, availability.id))

    assert winner.id == below_limit_application.id
    assert winner.id != at_limit_application.id


def test_applicant_below_soft_limit_ranks_before_applicant_above_soft_limit(db_session: Session) -> None:
    availability, above_limit_applicant, below_limit_applicant, above_limit_application, below_limit_application = (
        create_rankable_pair(db_session, suffix="softabove")
    )

    winner = ranking_service(
        recent_win_counts={
            above_limit_applicant.id: 3,
            below_limit_applicant.id: 1,
        },
    ).select_winning_application(availability, pending_applications(db_session, availability.id))

    assert winner.id == below_limit_application.id
    assert winner.id != above_limit_application.id


def test_fewer_recent_wins_wins_when_both_applicants_are_below_soft_limit(db_session: Session) -> None:
    availability, one_win_applicant, zero_win_applicant, one_win_application, zero_win_application = (
        create_rankable_pair(db_session, suffix="softbothbelow")
    )

    winner = ranking_service(
        recent_win_counts={
            one_win_applicant.id: 1,
            zero_win_applicant.id: 0,
        },
    ).select_winning_application(availability, pending_applications(db_session, availability.id))

    assert winner.id == zero_win_application.id
    assert winner.id != one_win_application.id


def test_fewer_recent_wins_wins_when_both_applicants_are_at_or_above_soft_limit(
    db_session: Session,
) -> None:
    availability, three_win_applicant, two_win_applicant, three_win_application, two_win_application = (
        create_rankable_pair(db_session, suffix="softbothabove")
    )

    winner = ranking_service(
        recent_win_counts={
            three_win_applicant.id: 3,
            two_win_applicant.id: 2,
        },
    ).select_winning_application(availability, pending_applications(db_session, availability.id))

    assert winner.id == two_win_application.id
    assert winner.id != three_win_application.id


def test_applicant_at_soft_limit_can_win_when_only_candidate(db_session: Session) -> None:
    owner = create_user(db_session, suffix="softonlyowner", role=UserRole.PARKING_OWNER)
    applicant = create_user(db_session, suffix="softonlyapplicant")
    availability = create_availability(db_session, suffix="softonly", owner_id=owner.id, priority_until=None)
    application = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=applicant.id,
        created_at=TEST_NOW,
    )

    winner = ranking_service(
        recent_win_counts={applicant.id: 2},
    ).select_winning_application(availability, pending_applications(db_session, availability.id))

    assert winner.id == application.id


def test_soft_limit_bucket_uses_custom_config_value() -> None:
    service = ranking_service(soft_limit=4)

    assert service._soft_limit_rank(3) == 0
    assert service._soft_limit_rank(4) == 1


def test_priority_until_none_means_no_same_team_priority(db_session: Session) -> None:
    owner_team = create_team(db_session, "none-owner")
    other_team = create_team(db_session, "none-other")
    owner = create_user(db_session, suffix="noneowner", role=UserRole.PARKING_OWNER, team_id=owner_team.id)
    same_team_applicant = create_user(db_session, suffix="nonesame", team_id=owner_team.id)
    non_team_applicant = create_user(db_session, suffix="nonenonteam", team_id=other_team.id)
    availability = create_availability(db_session, suffix="none", owner_id=owner.id, priority_until=None)
    older_non_team = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=non_team_applicant.id,
        created_at=TEST_NOW - timedelta(hours=2),
    )
    create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=same_team_applicant.id,
        created_at=TEST_NOW - timedelta(hours=1),
    )

    winner = ranking_service().select_winning_application(availability, pending_applications(db_session, availability.id))

    assert winner.id == older_non_team.id


def test_equal_created_at_falls_back_to_lowest_application_id(db_session: Session) -> None:
    owner = create_user(db_session, suffix="tieowner", role=UserRole.PARKING_OWNER)
    first_applicant = create_user(db_session, suffix="tiefirst")
    second_applicant = create_user(db_session, suffix="tiesecond")
    availability = create_availability(db_session, suffix="tie", owner_id=owner.id, priority_until=None)
    first_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=first_applicant.id,
        created_at=TEST_NOW,
    )
    second_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=second_applicant.id,
        created_at=TEST_NOW,
    )

    winner = ranking_service(
        recent_win_counts={
            first_applicant.id: 1,
            second_applicant.id: 1,
        },
    ).select_winning_application(availability, pending_applications(db_session, availability.id))

    assert first_application.id < second_application.id
    assert winner.id == first_application.id


def test_missing_applicant_in_recent_win_count_map_defaults_to_zero(db_session: Session) -> None:
    owner = create_user(db_session, suffix="missingcountowner", role=UserRole.PARKING_OWNER)
    counted_applicant = create_user(db_session, suffix="missingcountknown")
    missing_applicant = create_user(db_session, suffix="missingcountmissing")
    availability = create_availability(
        db_session,
        suffix="missingcount",
        owner_id=owner.id,
        priority_until=None,
    )
    earlier_counted = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=counted_applicant.id,
        created_at=TEST_NOW - timedelta(hours=2),
    )
    later_missing = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=missing_applicant.id,
        created_at=TEST_NOW - timedelta(hours=1),
    )

    winner = ranking_service(
        recent_win_counts={counted_applicant.id: 1},
    ).select_winning_application(availability, pending_applications(db_session, availability.id))

    assert winner.id == later_missing.id
    assert winner.id != earlier_counted.id


def test_recent_win_provider_receives_configured_lookback_boundary(db_session: Session) -> None:
    owner = create_user(db_session, suffix="lookbackowner", role=UserRole.PARKING_OWNER)
    applicant = create_user(db_session, suffix="lookbackapplicant")
    availability = create_availability(db_session, suffix="lookback", owner_id=owner.id, priority_until=None)
    application = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=applicant.id,
        created_at=TEST_NOW,
    )
    received_since: datetime | None = None

    def count_provider(user_ids: list[int], since: datetime) -> dict[int, int]:
        nonlocal received_since
        received_since = since
        return {user_id: 0 for user_id in user_ids}

    service = ParkingApplicationRankingService(
        now_provider=lambda: TEST_NOW,
        recent_win_count_provider=count_provider,
        settings=Settings(recent_win_fairness_window_days=7),
    )

    winner = service.select_winning_application(availability, pending_applications(db_session, availability.id))

    assert winner.id == application.id
    assert received_since == TEST_NOW - timedelta(days=7)


def test_ranking_audit_details_explain_candidate_order_during_team_priority_window(
    db_session: Session,
) -> None:
    owner_team = create_team(db_session, "audit-owner")
    other_team = create_team(db_session, "audit-other")
    owner = create_user(db_session, suffix="auditowner", role=UserRole.PARKING_OWNER, team_id=owner_team.id)
    same_team_applicant = create_user(db_session, suffix="auditsame", team_id=owner_team.id)
    non_team_applicant = create_user(db_session, suffix="auditnonteam", team_id=other_team.id)
    availability = create_availability(
        db_session,
        suffix="auditactive",
        owner_id=owner.id,
        priority_until=TEST_NOW,
    )
    earlier_non_team_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=non_team_applicant.id,
        created_at=TEST_NOW - timedelta(hours=2),
    )
    later_same_team_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=same_team_applicant.id,
        created_at=TEST_NOW - timedelta(hours=1),
    )

    result = ranking_service(
        recent_win_counts={
            same_team_applicant.id: 2,
            non_team_applicant.id: 0,
        },
    ).rank_applications_with_audit(availability, pending_applications(db_session, availability.id))

    assert result.selected_application.id == later_same_team_application.id
    assert [application.id for application in result.ranked_applications] == [
        later_same_team_application.id,
        earlier_non_team_application.id,
    ]
    assert [detail.application_id for detail in result.audit_details] == [
        later_same_team_application.id,
        earlier_non_team_application.id,
    ]
    selected_detail, rejected_detail = result.audit_details
    assert selected_detail.applicant_id == same_team_applicant.id
    assert selected_detail.applicant_team_id == owner_team.id
    assert selected_detail.owner_team_id == owner_team.id
    assert selected_detail.is_same_team_as_owner is True
    assert selected_detail.team_priority_active is True
    assert selected_detail.recent_win_count == 2
    assert selected_detail.is_over_soft_limit is True
    assert selected_detail.application_created_at == TEST_NOW - timedelta(hours=1)
    assert selected_detail.ranking_order_values == (
        0,
        1,
        2,
        TEST_NOW - timedelta(hours=1),
        later_same_team_application.id,
    )
    assert selected_detail.final_rank_position == 1
    assert selected_detail.selected is True
    assert rejected_detail.applicant_id == non_team_applicant.id
    assert rejected_detail.is_same_team_as_owner is False
    assert rejected_detail.team_priority_active is True
    assert rejected_detail.recent_win_count == 0
    assert rejected_detail.is_over_soft_limit is False
    assert rejected_detail.final_rank_position == 2
    assert rejected_detail.selected is False


def test_ranking_audit_details_show_team_priority_inactive_after_window(db_session: Session) -> None:
    owner_team = create_team(db_session, "audit-after-owner")
    other_team = create_team(db_session, "audit-after-other")
    owner = create_user(db_session, suffix="auditafterowner", role=UserRole.PARKING_OWNER, team_id=owner_team.id)
    same_team_applicant = create_user(db_session, suffix="auditaftersame", team_id=owner_team.id)
    non_team_applicant = create_user(db_session, suffix="auditafternonteam", team_id=other_team.id)
    availability = create_availability(
        db_session,
        suffix="auditafter",
        owner_id=owner.id,
        priority_until=TEST_NOW - timedelta(minutes=1),
    )
    same_team_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=same_team_applicant.id,
        created_at=TEST_NOW - timedelta(hours=2),
    )
    non_team_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=non_team_applicant.id,
        created_at=TEST_NOW - timedelta(hours=1),
    )

    result = ranking_service(
        recent_win_counts={
            same_team_applicant.id: 1,
            non_team_applicant.id: 0,
        },
    ).rank_applications_with_audit(availability, pending_applications(db_session, availability.id))

    assert result.selected_application.id == non_team_application.id
    assert [detail.team_priority_active for detail in result.audit_details] == [False, False]
    assert [detail.ranking_order_values[0] for detail in result.audit_details] == [1, 1]
    assert {
        detail.application_id: detail.is_same_team_as_owner for detail in result.audit_details
    } == {
        same_team_application.id: True,
        non_team_application.id: False,
    }


def test_repository_pending_filter_excludes_cancelled_rejected_and_selected_applications(
    db_session: Session,
) -> None:
    owner = create_user(db_session, suffix="filterowner", role=UserRole.PARKING_OWNER)
    pending_applicant = create_user(db_session, suffix="filterpending")
    cancelled_applicant = create_user(db_session, suffix="filtercancelled")
    rejected_applicant = create_user(db_session, suffix="filterrejected")
    selected_applicant = create_user(db_session, suffix="filterselected")
    availability = create_availability(db_session, suffix="filter", owner_id=owner.id, priority_until=None)
    pending_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=pending_applicant.id,
        created_at=TEST_NOW,
    )
    create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=cancelled_applicant.id,
        created_at=TEST_NOW - timedelta(hours=3),
        status=ParkingApplicationStatus.CANCELLED,
    )
    create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=rejected_applicant.id,
        created_at=TEST_NOW - timedelta(hours=2),
        status=ParkingApplicationStatus.REJECTED,
    )
    create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=selected_applicant.id,
        created_at=TEST_NOW - timedelta(hours=1),
        status=ParkingApplicationStatus.SELECTED,
    )

    ranked = ranking_service().rank_applications_for_availability(
        availability,
        pending_applications(db_session, availability.id),
    )

    assert [application.id for application in ranked] == [pending_application.id]
