from collections.abc import Generator

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
from app.models.parking_spot import ParkingSpot
from app.models.user import User, UserRole
from app.repositories.parking_spots import ParkingSpotRepository
from app.repositories.users import UserRepository


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
    email: str,
    username: str,
    role: UserRole = UserRole.EMPLOYEE,
    is_active: bool = True,
) -> User:
    repository = UserRepository(db_session)
    user = repository.create(
        email=email,
        username=username,
        first_name="Test",
        last_name="User",
        hashed_password=hash_password("valid-password"),
        role=role,
        is_active=is_active,
    )
    db_session.commit()
    return user


def create_admin(db_session: Session) -> User:
    return create_test_user(
        db_session,
        email="admin@example.com",
        username="admin",
        role=UserRole.ADMIN,
    )


def create_owner(
    db_session: Session,
    *,
    email: str = "owner@example.com",
    username: str = "owner",
    is_active: bool = True,
) -> User:
    return create_test_user(
        db_session,
        email=email,
        username=username,
        role=UserRole.PARKING_OWNER,
        is_active=is_active,
    )


def create_test_parking_spot(
    db_session: Session,
    *,
    code: str,
    owner_id: int | None = None,
    is_active: bool = True,
) -> ParkingSpot:
    repository = ParkingSpotRepository(db_session)
    parking_spot = repository.create(
        code=code,
        location="Garage P1",
        description="Near elevator",
        owner_id=owner_id,
        is_active=is_active,
    )
    db_session.commit()
    return parking_spot


def bearer_header(user: User) -> dict[str, str]:
    token = create_access_token(subject=user.id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


def parking_spot_payload(
    *,
    code: str = "A-12",
    owner_id: int | None = None,
    is_active: bool = True,
) -> dict[str, str | int | bool | None]:
    return {
        "code": code,
        "location": "Garage P1",
        "description": "Near elevator",
        "owner_id": owner_id,
        "is_active": is_active,
    }


def assert_no_sensitive_user_fields(payload: dict[str, object]) -> None:
    assert "owner" not in payload
    assert "hashed_password" not in payload
    assert "password" not in payload


def test_admin_can_create_parking_spot_without_owner(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)

    response = client.post(
        "/admin/parking-spots",
        json=parking_spot_payload(),
        headers=bearer_header(admin),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["code"] == "A-12"
    assert body["owner_id"] is None
    assert body["is_active"] is True
    assert_no_sensitive_user_fields(body)


def test_admin_can_create_parking_spot_with_active_owner(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    owner = create_owner(db_session)

    response = client.post(
        "/admin/parking-spots",
        json=parking_spot_payload(owner_id=owner.id),
        headers=bearer_header(admin),
    )

    assert response.status_code == 201
    assert response.json()["owner_id"] == owner.id


def test_create_parking_spot_with_missing_owner_returns_404(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)

    response = client.post(
        "/admin/parking-spots",
        json=parking_spot_payload(owner_id=999),
        headers=bearer_header(admin),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Owner not found"}


def test_create_parking_spot_with_inactive_owner_returns_400(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    inactive_owner = create_owner(
        db_session,
        email="inactive.owner@example.com",
        username="inactiveowner",
        is_active=False,
    )

    response = client.post(
        "/admin/parking-spots",
        json=parking_spot_payload(owner_id=inactive_owner.id),
        headers=bearer_header(admin),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Owner is inactive"}


def test_create_duplicate_parking_spot_code_returns_409(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    create_test_parking_spot(db_session, code="A-12")

    response = client.post(
        "/admin/parking-spots",
        json=parking_spot_payload(code="A-12"),
        headers=bearer_header(admin),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Parking spot code already exists"}


def test_admin_can_list_parking_spots(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    create_test_parking_spot(db_session, code="A-12")
    create_test_parking_spot(db_session, code="A-13")

    response = client.get("/admin/parking-spots", headers=bearer_header(admin))

    assert response.status_code == 200
    body = response.json()
    assert [parking_spot["code"] for parking_spot in body] == ["A-12", "A-13"]
    for parking_spot in body:
        assert_no_sensitive_user_fields(parking_spot)


def test_admin_can_filter_parking_spots_by_owner_id(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    owner = create_owner(db_session)
    other_owner = create_owner(
        db_session,
        email="other.owner@example.com",
        username="otherowner",
    )
    create_test_parking_spot(db_session, code="A-12", owner_id=owner.id)
    create_test_parking_spot(db_session, code="A-13", owner_id=owner.id)
    create_test_parking_spot(db_session, code="B-01", owner_id=other_owner.id)

    response = client.get(f"/admin/parking-spots?owner_id={owner.id}", headers=bearer_header(admin))

    assert response.status_code == 200
    assert [parking_spot["code"] for parking_spot in response.json()] == ["A-12", "A-13"]


def test_admin_can_filter_parking_spots_by_active_status(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    create_test_parking_spot(db_session, code="A-12", is_active=True)
    create_test_parking_spot(db_session, code="A-13", is_active=False)

    response = client.get("/admin/parking-spots?is_active=false", headers=bearer_header(admin))

    assert response.status_code == 200
    assert [parking_spot["code"] for parking_spot in response.json()] == ["A-13"]


def test_admin_can_get_parking_spot_by_id(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    parking_spot = create_test_parking_spot(db_session, code="A-12")

    response = client.get(f"/admin/parking-spots/{parking_spot.id}", headers=bearer_header(admin))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == parking_spot.id
    assert body["code"] == "A-12"
    assert_no_sensitive_user_fields(body)


def test_get_missing_parking_spot_returns_404(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)

    response = client.get("/admin/parking-spots/999", headers=bearer_header(admin))

    assert response.status_code == 404
    assert response.json() == {"detail": "Parking spot not found"}


def test_admin_can_update_parking_spot_basic_fields(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    parking_spot = create_test_parking_spot(db_session, code="A-12", is_active=True)

    response = client.patch(
        f"/admin/parking-spots/{parking_spot.id}",
        json={
            "code": "A-14",
            "location": "Garage P2",
            "description": None,
            "is_active": False,
        },
        headers=bearer_header(admin),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "A-14"
    assert body["location"] == "Garage P2"
    assert body["description"] is None
    assert body["is_active"] is False


def test_admin_can_assign_owner(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    owner = create_owner(db_session)
    parking_spot = create_test_parking_spot(db_session, code="A-12")

    response = client.patch(
        f"/admin/parking-spots/{parking_spot.id}",
        json={"owner_id": owner.id},
        headers=bearer_header(admin),
    )

    assert response.status_code == 200
    assert response.json()["owner_id"] == owner.id


def test_admin_can_unassign_owner(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    owner = create_owner(db_session)
    parking_spot = create_test_parking_spot(db_session, code="A-12", owner_id=owner.id)

    response = client.patch(
        f"/admin/parking-spots/{parking_spot.id}",
        json={"owner_id": None},
        headers=bearer_header(admin),
    )

    assert response.status_code == 200
    assert response.json()["owner_id"] is None


def test_update_parking_spot_with_missing_owner_returns_404(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    parking_spot = create_test_parking_spot(db_session, code="A-12")

    response = client.patch(
        f"/admin/parking-spots/{parking_spot.id}",
        json={"owner_id": 999},
        headers=bearer_header(admin),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Owner not found"}


def test_update_parking_spot_with_inactive_owner_returns_400(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    inactive_owner = create_owner(
        db_session,
        email="inactive.owner@example.com",
        username="inactiveowner",
        is_active=False,
    )
    parking_spot = create_test_parking_spot(db_session, code="A-12")

    response = client.patch(
        f"/admin/parking-spots/{parking_spot.id}",
        json={"owner_id": inactive_owner.id},
        headers=bearer_header(admin),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Owner is inactive"}


def test_update_missing_parking_spot_returns_404(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)

    response = client.patch(
        "/admin/parking-spots/999",
        json={"code": "A-14"},
        headers=bearer_header(admin),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Parking spot not found"}


def test_update_duplicate_parking_spot_code_returns_409(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    create_test_parking_spot(db_session, code="A-12")
    parking_spot = create_test_parking_spot(db_session, code="A-13")

    response = client.patch(
        f"/admin/parking-spots/{parking_spot.id}",
        json={"code": "A-12"},
        headers=bearer_header(admin),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Parking spot code already exists"}


def test_admin_can_delete_parking_spot(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    parking_spot = create_test_parking_spot(db_session, code="A-12")

    response = client.delete(f"/admin/parking-spots/{parking_spot.id}", headers=bearer_header(admin))

    assert response.status_code == 204
    assert response.content == b""
    assert ParkingSpotRepository(db_session).get_by_id(parking_spot.id) is None


def test_delete_missing_parking_spot_returns_404(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)

    response = client.delete("/admin/parking-spots/999", headers=bearer_header(admin))

    assert response.status_code == 404
    assert response.json() == {"detail": "Parking spot not found"}


def test_employee_cannot_access_admin_parking_spot_routes(client: TestClient, db_session: Session) -> None:
    employee = create_test_user(
        db_session,
        email="employee@example.com",
        username="employee",
    )

    response = client.get("/admin/parking-spots", headers=bearer_header(employee))

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}


def test_parking_owner_cannot_access_admin_parking_spot_routes(client: TestClient, db_session: Session) -> None:
    parking_owner = create_owner(db_session)

    response = client.get("/admin/parking-spots", headers=bearer_header(parking_owner))

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}


def test_missing_token_returns_401(client: TestClient) -> None:
    response = client.get("/admin/parking-spots")

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


def test_invalid_token_returns_401(client: TestClient) -> None:
    response = client.get("/admin/parking-spots", headers={"Authorization": "Bearer invalid-token"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}
