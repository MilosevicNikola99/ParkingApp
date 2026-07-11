from collections.abc import Generator

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.security import create_access_token, hash_password, verify_password
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models.team import Team
from app.models.user import User, UserRole
from app.repositories.teams import TeamRepository
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
    password: str = "valid-password",
    team_id: int | None = None,
    is_active: bool = True,
) -> User:
    repository = UserRepository(db_session)
    user = repository.create(
        email=email,
        username=username,
        first_name="Test",
        last_name="User",
        hashed_password=hash_password(password),
        role=role,
        team_id=team_id,
        is_active=is_active,
    )
    db_session.commit()
    return user


def create_test_team(db_session: Session, *, name: str = "Engineering") -> Team:
    repository = TeamRepository(db_session)
    team = repository.create(name=name)
    db_session.commit()
    return team


def create_admin(db_session: Session) -> User:
    return create_test_user(
        db_session,
        email="admin@example.com",
        username="admin",
        role=UserRole.ADMIN,
    )


def bearer_header(user: User) -> dict[str, str]:
    token = create_access_token(subject=user.id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


def user_payload(
    *,
    email: str = "employee@example.com",
    username: str = "employee",
    password: str = "new-user-password",
    team_id: int | None = None,
) -> dict[str, str | int | bool | None]:
    return {
        "email": email,
        "username": username,
        "first_name": "Ada",
        "last_name": "Lovelace",
        "password": password,
        "role": "employee",
        "team_id": team_id,
        "is_active": True,
    }


def assert_no_password_fields(payload: dict[str, object]) -> None:
    assert "hashed_password" not in payload
    assert "password" not in payload


def test_admin_can_create_user_without_team(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)

    response = client.post(
        "/admin/users",
        json=user_payload(),
        headers=bearer_header(admin),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "employee@example.com"
    assert body["username"] == "employee"
    assert body["team_id"] is None
    assert_no_password_fields(body)


def test_admin_can_create_user_with_existing_team(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    team = create_test_team(db_session)

    response = client.post(
        "/admin/users",
        json=user_payload(team_id=team.id),
        headers=bearer_header(admin),
    )

    assert response.status_code == 201
    assert response.json()["team_id"] == team.id


def test_create_user_with_missing_team_returns_404(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)

    response = client.post(
        "/admin/users",
        json=user_payload(team_id=999),
        headers=bearer_header(admin),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Team not found"}


def test_create_duplicate_email_returns_409(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    create_test_user(db_session, email="employee@example.com", username="existing")

    response = client.post(
        "/admin/users",
        json=user_payload(username="newusername"),
        headers=bearer_header(admin),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Email already exists"}


def test_create_duplicate_username_returns_409(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    create_test_user(db_session, email="existing@example.com", username="employee")

    response = client.post(
        "/admin/users",
        json=user_payload(email="new@example.com"),
        headers=bearer_header(admin),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Username already exists"}


def test_admin_can_list_users(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    create_test_user(db_session, email="employee@example.com", username="employee")
    create_test_user(
        db_session,
        email="owner@example.com",
        username="owner",
        role=UserRole.PARKING_OWNER,
    )

    response = client.get("/admin/users", headers=bearer_header(admin))

    assert response.status_code == 200
    body = response.json()
    assert [user["username"] for user in body] == ["admin", "employee", "owner"]
    for user in body:
        assert_no_password_fields(user)


def test_admin_can_list_users_by_team_id(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    team = create_test_team(db_session)
    create_test_user(db_session, email="team@example.com", username="teamuser", team_id=team.id)
    create_test_user(db_session, email="other@example.com", username="otheruser")

    response = client.get(f"/admin/users?team_id={team.id}", headers=bearer_header(admin))

    assert response.status_code == 200
    assert [user["username"] for user in response.json()] == ["teamuser"]


def test_admin_can_get_user_by_id(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    user = create_test_user(db_session, email="employee@example.com", username="employee")

    response = client.get(f"/admin/users/{user.id}", headers=bearer_header(admin))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == user.id
    assert body["email"] == "employee@example.com"
    assert_no_password_fields(body)


def test_get_missing_user_returns_404(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)

    response = client.get("/admin/users/999", headers=bearer_header(admin))

    assert response.status_code == 404
    assert response.json() == {"detail": "User not found"}


def test_admin_can_update_user_basic_fields(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    user = create_test_user(db_session, email="employee@example.com", username="employee")

    response = client.patch(
        f"/admin/users/{user.id}",
        json={
            "email": "updated@example.com",
            "username": "updated",
            "first_name": "Grace",
            "last_name": "Hopper",
            "role": "parking_owner",
            "is_active": False,
        },
        headers=bearer_header(admin),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "updated@example.com"
    assert body["username"] == "updated"
    assert body["first_name"] == "Grace"
    assert body["last_name"] == "Hopper"
    assert body["role"] == "parking_owner"
    assert body["is_active"] is False
    assert_no_password_fields(body)


def test_admin_can_update_user_team_id(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    team = create_test_team(db_session)
    user = create_test_user(db_session, email="employee@example.com", username="employee")

    response = client.patch(
        f"/admin/users/{user.id}",
        json={"team_id": team.id},
        headers=bearer_header(admin),
    )

    assert response.status_code == 200
    assert response.json()["team_id"] == team.id


def test_admin_can_clear_user_team_id(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    team = create_test_team(db_session)
    user = create_test_user(
        db_session,
        email="employee@example.com",
        username="employee",
        team_id=team.id,
    )

    response = client.patch(
        f"/admin/users/{user.id}",
        json={"team_id": None},
        headers=bearer_header(admin),
    )

    assert response.status_code == 200
    assert response.json()["team_id"] is None


def test_update_user_with_missing_team_returns_404(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    user = create_test_user(db_session, email="employee@example.com", username="employee")

    response = client.patch(
        f"/admin/users/{user.id}",
        json={"team_id": 999},
        headers=bearer_header(admin),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Team not found"}


def test_update_missing_user_returns_404(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)

    response = client.patch(
        "/admin/users/999",
        json={"first_name": "Missing"},
        headers=bearer_header(admin),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "User not found"}


def test_update_duplicate_email_returns_409(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    create_test_user(db_session, email="existing@example.com", username="existing")
    user = create_test_user(db_session, email="employee@example.com", username="employee")

    response = client.patch(
        f"/admin/users/{user.id}",
        json={"email": "existing@example.com"},
        headers=bearer_header(admin),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Email already exists"}


def test_update_duplicate_username_returns_409(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    create_test_user(db_session, email="existing@example.com", username="existing")
    user = create_test_user(db_session, email="employee@example.com", username="employee")

    response = client.patch(
        f"/admin/users/{user.id}",
        json={"username": "existing"},
        headers=bearer_header(admin),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Username already exists"}


def test_admin_can_update_user_password_and_stores_hash(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    user = create_test_user(
        db_session,
        email="employee@example.com",
        username="employee",
        password="old-password",
    )

    response = client.patch(
        f"/admin/users/{user.id}",
        json={"password": "new-password"},
        headers=bearer_header(admin),
    )

    assert response.status_code == 200
    assert_no_password_fields(response.json())

    stored_user = UserRepository(db_session).get_by_id(user.id)
    assert stored_user is not None
    assert stored_user.hashed_password != "new-password"
    assert verify_password("new-password", stored_user.hashed_password)


def test_admin_can_delete_user(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    user = create_test_user(db_session, email="employee@example.com", username="employee")

    response = client.delete(f"/admin/users/{user.id}", headers=bearer_header(admin))

    assert response.status_code == 204
    assert response.content == b""
    assert UserRepository(db_session).get_by_id(user.id) is None


def test_delete_missing_user_returns_404(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)

    response = client.delete("/admin/users/999", headers=bearer_header(admin))

    assert response.status_code == 404
    assert response.json() == {"detail": "User not found"}


def test_admin_cannot_delete_own_account(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)

    response = client.delete(f"/admin/users/{admin.id}", headers=bearer_header(admin))

    assert response.status_code == 400
    assert response.json() == {"detail": "Admins cannot delete their own account"}
    assert UserRepository(db_session).get_by_id(admin.id) is not None


def test_employee_cannot_access_admin_user_routes(client: TestClient, db_session: Session) -> None:
    employee = create_test_user(
        db_session,
        email="employee@example.com",
        username="employee",
    )

    response = client.get("/admin/users", headers=bearer_header(employee))

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}


def test_parking_owner_cannot_access_admin_user_routes(client: TestClient, db_session: Session) -> None:
    parking_owner = create_test_user(
        db_session,
        email="owner@example.com",
        username="owner",
        role=UserRole.PARKING_OWNER,
    )

    response = client.get("/admin/users", headers=bearer_header(parking_owner))

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}


def test_missing_token_returns_401(client: TestClient) -> None:
    response = client.get("/admin/users")

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


def test_invalid_token_returns_401(client: TestClient) -> None:
    response = client.get("/admin/users", headers={"Authorization": "Bearer invalid-token"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


def test_created_user_password_is_hashed(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    plain_password = "plain-password"

    response = client.post(
        "/admin/users",
        json=user_payload(password=plain_password),
        headers=bearer_header(admin),
    )

    assert response.status_code == 201
    stored_user = UserRepository(db_session).get_by_username("employee")
    assert stored_user is not None
    assert stored_user.hashed_password != plain_password
    assert verify_password(plain_password, stored_user.hashed_password)
