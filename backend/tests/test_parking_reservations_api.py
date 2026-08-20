from collections.abc import Generator
from datetime import UTC, datetime, timedelta
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models.parking_application import ParkingApplication, ParkingApplicationStatus
from app.models.parking_availability import ParkingAvailability, ParkingAvailabilityStatus
from app.models.parking_reservation import ParkingReservation, ParkingReservationStatus
from app.models.parking_spot import ParkingSpot
from app.models.user import User, UserRole
from app.repositories.parking_applications import ParkingApplicationRepository
from app.repositories.parking_availabilities import ParkingAvailabilityRepository
from app.repositories.parking_reservations import ParkingReservationRepository
from app.repositories.parking_spots import ParkingSpotRepository
from app.repositories.users import UserRepository

TEST_NOW = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def app_with_db(db_session: Session) -> Generator[FastAPI, None, None]:
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture()
def client(app_with_db: FastAPI) -> TestClient:
    return TestClient(app_with_db)


def create_test_user(
    db_session: Session,
    *,
    suffix: str,
    role: UserRole = UserRole.EMPLOYEE,
) -> User:
    user = UserRepository(db_session).create(
        email=f"reservation.{suffix}@example.com",
        username=f"reservation{suffix}",
        first_name="Test",
        last_name="User",
        hashed_password=hash_password("valid-password"),
        role=role,
    )
    db_session.flush()
    return user


def create_owner(db_session: Session, suffix: str) -> User:
    return create_test_user(db_session, suffix=suffix, role=UserRole.PARKING_OWNER)


def create_employee(db_session: Session, suffix: str) -> User:
    return create_test_user(db_session, suffix=suffix)


def create_admin(db_session: Session, suffix: str = "admin") -> User:
    return create_test_user(db_session, suffix=suffix, role=UserRole.ADMIN)


def create_parking_spot(db_session: Session, *, owner_id: int, code: str) -> ParkingSpot:
    return ParkingSpotRepository(db_session).create(
        code=code,
        location="Garage P1",
        owner_id=owner_id,
    )


def create_availability(
    db_session: Session,
    *,
    parking_spot_id: int,
    owner_id: int,
    start_at: datetime,
) -> ParkingAvailability:
    return ParkingAvailabilityRepository(db_session).create(
        parking_spot_id=parking_spot_id,
        owner_id=owner_id,
        start_at=start_at,
        end_at=start_at + timedelta(hours=4),
        status=ParkingAvailabilityStatus.ASSIGNED,
    )


def create_application(
    db_session: Session,
    *,
    availability_id: int,
    applicant_id: int,
) -> ParkingApplication:
    return ParkingApplicationRepository(db_session).create(
        availability_id=availability_id,
        applicant_id=applicant_id,
        status=ParkingApplicationStatus.SELECTED,
        note="Selected application",
    )


def create_reservation_context(
    db_session: Session,
    *,
    suffix: str,
    owner: User | None = None,
    reserved_for_user: User | None = None,
    status: ParkingReservationStatus = ParkingReservationStatus.ACTIVE,
    start_at: datetime | None = None,
) -> tuple[User, User, ParkingSpot, ParkingAvailability, ParkingApplication, ParkingReservation]:
    owner = owner or create_owner(db_session, f"owner{suffix}")
    reserved_for_user = reserved_for_user or create_employee(db_session, f"employee{suffix}")
    start = start_at or TEST_NOW
    parking_spot = create_parking_spot(db_session, owner_id=owner.id, code=f"R-{suffix}")
    availability = create_availability(
        db_session,
        parking_spot_id=parking_spot.id,
        owner_id=owner.id,
        start_at=start,
    )
    application = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=reserved_for_user.id,
    )
    reservation = ParkingReservationRepository(db_session).create(
        availability_id=availability.id,
        application_id=application.id,
        parking_spot_id=parking_spot.id,
        reserved_for_user_id=reserved_for_user.id,
        start_at=availability.start_at,
        end_at=availability.end_at,
        status=status,
    )
    db_session.commit()
    db_session.refresh(reservation)
    return owner, reserved_for_user, parking_spot, availability, application, reservation


def create_reservation_history_context(
    db_session: Session,
    *,
    suffix: str,
) -> tuple[ParkingAvailability, ParkingReservation, ParkingReservation]:
    owner = create_owner(db_session, f"historyowner{suffix}")
    previous_user = create_employee(db_session, f"historyprevious{suffix}")
    current_user = create_employee(db_session, f"historycurrent{suffix}")
    parking_spot = create_parking_spot(db_session, owner_id=owner.id, code=f"RH-{suffix}")
    availability = create_availability(
        db_session,
        parking_spot_id=parking_spot.id,
        owner_id=owner.id,
        start_at=TEST_NOW,
    )
    previous_application = ParkingApplicationRepository(db_session).create(
        availability_id=availability.id,
        applicant_id=previous_user.id,
        status=ParkingApplicationStatus.CANCELLED,
    )
    current_application = ParkingApplicationRepository(db_session).create(
        availability_id=availability.id,
        applicant_id=current_user.id,
        status=ParkingApplicationStatus.SELECTED,
    )
    repository = ParkingReservationRepository(db_session)
    previous_reservation = repository.create(
        availability_id=availability.id,
        application_id=previous_application.id,
        parking_spot_id=parking_spot.id,
        reserved_for_user_id=previous_user.id,
        start_at=availability.start_at,
        end_at=availability.end_at,
        status=ParkingReservationStatus.CANCELLED,
    )
    current_reservation = repository.create(
        availability_id=availability.id,
        application_id=current_application.id,
        parking_spot_id=parking_spot.id,
        reserved_for_user_id=current_user.id,
        start_at=availability.start_at,
        end_at=availability.end_at,
    )
    db_session.commit()
    return availability, previous_reservation, current_reservation


def bearer_header(user: User) -> dict[str, str]:
    token = create_access_token(subject=user.id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


def assert_no_sensitive_fields(payload: dict[str, object]) -> None:
    assert "availability" not in payload
    assert "application" not in payload
    assert payload["parking_spot"]["code"]
    assert payload["reserved_for_user"]["email"]
    serialized_payload = json.dumps(payload)
    assert "hashed_password" not in serialized_payload
    assert "password" not in serialized_payload


def test_authenticated_user_can_list_own_reservations(client: TestClient, db_session: Session) -> None:
    reserved_for_user = create_employee(db_session, "listown")
    other_user = create_employee(db_session, "listother")
    _, _, _, _, _, first = create_reservation_context(
        db_session,
        suffix="listfirst",
        reserved_for_user=reserved_for_user,
        start_at=TEST_NOW,
    )
    _, _, _, _, _, second = create_reservation_context(
        db_session,
        suffix="listsecond",
        reserved_for_user=reserved_for_user,
        start_at=TEST_NOW + timedelta(days=1),
    )
    create_reservation_context(
        db_session,
        suffix="listthird",
        reserved_for_user=other_user,
        start_at=TEST_NOW + timedelta(days=2),
    )

    response = client.get("/parking-reservations/my", headers=bearer_header(reserved_for_user))

    assert response.status_code == 200
    body = response.json()
    assert [reservation["id"] for reservation in body] == [first.id, second.id]
    assert all(reservation["reserved_for_user_id"] == reserved_for_user.id for reservation in body)
    assert_no_sensitive_fields(body[0])


def test_my_reservations_status_filter_works(client: TestClient, db_session: Session) -> None:
    reserved_for_user = create_employee(db_session, "filteruser")
    create_reservation_context(
        db_session,
        suffix="filteractive",
        reserved_for_user=reserved_for_user,
        status=ParkingReservationStatus.ACTIVE,
        start_at=TEST_NOW,
    )
    _, _, _, _, _, completed = create_reservation_context(
        db_session,
        suffix="filtercompleted",
        reserved_for_user=reserved_for_user,
        status=ParkingReservationStatus.COMPLETED,
        start_at=TEST_NOW + timedelta(days=1),
    )

    response = client.get(
        "/parking-reservations/my?status=completed",
        headers=bearer_header(reserved_for_user),
    )

    assert response.status_code == 200
    assert [reservation["id"] for reservation in response.json()] == [completed.id]


def test_user_can_view_own_reservation(client: TestClient, db_session: Session) -> None:
    _, reserved_for_user, _, _, _, reservation = create_reservation_context(db_session, suffix="ownview")

    response = client.get(f"/parking-reservations/{reservation.id}", headers=bearer_header(reserved_for_user))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == reservation.id
    assert body["reserved_for_user_id"] == reserved_for_user.id
    assert_no_sensitive_fields(body)


def test_availability_owner_can_view_reservation_for_published_availability(
    client: TestClient,
    db_session: Session,
) -> None:
    owner, _, _, _, _, reservation = create_reservation_context(db_session, suffix="ownerview")

    response = client.get(f"/parking-reservations/{reservation.id}", headers=bearer_header(owner))

    assert response.status_code == 200
    assert response.json()["id"] == reservation.id


def test_admin_can_view_any_reservation(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    _, _, _, _, _, reservation = create_reservation_context(db_session, suffix="adminview")

    response = client.get(f"/parking-reservations/{reservation.id}", headers=bearer_header(admin))

    assert response.status_code == 200
    assert response.json()["id"] == reservation.id


def test_unrelated_user_cannot_view_another_users_reservation(
    client: TestClient,
    db_session: Session,
) -> None:
    unrelated_user = create_employee(db_session, "unrelated")
    _, _, _, _, _, reservation = create_reservation_context(db_session, suffix="private")

    response = client.get(f"/parking-reservations/{reservation.id}", headers=bearer_header(unrelated_user))

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}


def test_missing_reservation_returns_404(client: TestClient, db_session: Session) -> None:
    user = create_employee(db_session, "missing")

    response = client.get("/parking-reservations/999", headers=bearer_header(user))

    assert response.status_code == 404
    assert response.json() == {"detail": "Parking reservation not found"}


def test_missing_token_returns_401(client: TestClient) -> None:
    response = client.get("/parking-reservations/my")

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


def test_invalid_token_returns_401(client: TestClient) -> None:
    response = client.get("/parking-reservations/my", headers={"Authorization": "Bearer invalid-token"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


def test_admin_can_list_reservations_with_filters(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    reserved_for_user = create_employee(db_session, "adminfilteruser")
    _, _, matching_spot, _, _, matching = create_reservation_context(
        db_session,
        suffix="adminfiltermatch",
        reserved_for_user=reserved_for_user,
        status=ParkingReservationStatus.COMPLETED,
        start_at=TEST_NOW,
    )
    create_reservation_context(
        db_session,
        suffix="adminfilterstatus",
        reserved_for_user=reserved_for_user,
        status=ParkingReservationStatus.ACTIVE,
        start_at=TEST_NOW + timedelta(days=1),
    )
    create_reservation_context(
        db_session,
        suffix="adminfilteruser",
        status=ParkingReservationStatus.COMPLETED,
        start_at=TEST_NOW + timedelta(days=2),
    )

    response = client.get(
        "/admin/parking-reservations"
        f"?status=completed&reserved_for_user_id={reserved_for_user.id}&parking_spot_id={matching_spot.id}",
        headers=bearer_header(admin),
    )

    assert response.status_code == 200
    assert [reservation["id"] for reservation in response.json()] == [matching.id]


def test_non_admin_cannot_access_admin_reservation_list(client: TestClient, db_session: Session) -> None:
    employee = create_employee(db_session, "notadmin")

    response = client.get("/admin/parking-reservations", headers=bearer_header(employee))

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}


def test_admin_can_list_reservation_history_by_availability_with_explicit_lifecycle_state(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = create_admin(db_session, "historyadmin")
    availability, previous_reservation, current_reservation = create_reservation_history_context(
        db_session,
        suffix="filtered",
    )
    create_reservation_history_context(db_session, suffix="other")

    response = client.get(
        f"/admin/parking-reservations/history?availability_id={availability.id}",
        headers=bearer_header(admin),
    )

    assert response.status_code == 200
    body = response.json()
    assert [reservation["id"] for reservation in body] == [current_reservation.id, previous_reservation.id]
    assert [reservation["history_state"] for reservation in body] == ["current_active", "historical"]
    assert all(reservation["availability_id"] == availability.id for reservation in body)
    assert_no_sensitive_fields(body[0])


def test_admin_reservation_history_current_active_and_status_filters_work(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = create_admin(db_session, "historyfilteradmin")
    availability, previous_reservation, current_reservation = create_reservation_history_context(
        db_session,
        suffix="states",
    )

    current_response = client.get(
        f"/admin/parking-reservations/history?availability_id={availability.id}&current_active=true",
        headers=bearer_header(admin),
    )
    historical_response = client.get(
        f"/admin/parking-reservations/history?availability_id={availability.id}&current_active=false",
        headers=bearer_header(admin),
    )
    cancelled_response = client.get(
        f"/admin/parking-reservations/history?availability_id={availability.id}&status=cancelled",
        headers=bearer_header(admin),
    )

    assert current_response.status_code == 200
    assert [reservation["id"] for reservation in current_response.json()] == [current_reservation.id]
    assert historical_response.status_code == 200
    assert [reservation["id"] for reservation in historical_response.json()] == [previous_reservation.id]
    assert cancelled_response.status_code == 200
    assert [reservation["id"] for reservation in cancelled_response.json()] == [previous_reservation.id]


@pytest.mark.parametrize(
    ("headers", "expected_status", "expected_detail"),
    [
        ({}, 401, "Could not validate credentials"),
        ({"Authorization": "Bearer invalid-token"}, 401, "Could not validate credentials"),
    ],
)
def test_admin_reservation_history_requires_valid_token(
    client: TestClient,
    headers: dict[str, str],
    expected_status: int,
    expected_detail: str,
) -> None:
    response = client.get("/admin/parking-reservations/history", headers=headers)

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}


def test_non_admin_cannot_access_admin_reservation_history(client: TestClient, db_session: Session) -> None:
    employee = create_employee(db_session, "historynotadmin")

    response = client.get("/admin/parking-reservations/history", headers=bearer_header(employee))

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}


def test_admin_reservation_history_is_registered_with_bearer_security(app_with_db: FastAPI) -> None:
    operation = app_with_db.openapi()["paths"]["/admin/parking-reservations/history"]["get"]

    assert operation["security"] == [{"OAuth2PasswordBearer": []}]
    assert "availability_id" in {parameter["name"] for parameter in operation["parameters"]}
    assert "current_active" in {parameter["name"] for parameter in operation["parameters"]}
    assert "200" in operation["responses"]
    assert "422" in operation["responses"]
