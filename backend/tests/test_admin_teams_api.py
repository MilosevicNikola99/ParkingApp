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
    role: UserRole,
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


def create_test_team(
    db_session: Session,
    *,
    name: str,
    description: str | None = None,
) -> Team:
    repository = TeamRepository(db_session)
    team = repository.create(name=name, description=description)
    db_session.commit()
    return team


def bearer_header(user: User) -> dict[str, str]:
    token = create_access_token(subject=user.id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


def create_admin(db_session: Session) -> User:
    return create_test_user(
        db_session,
        email="admin@example.com",
        username="admin",
        role=UserRole.ADMIN,
    )


def test_admin_can_create_team(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)

    response = client.post(
        "/admin/teams",
        json={"name": "Engineering", "description": "Product engineers"},
        headers=bearer_header(admin),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["name"] == "Engineering"
    assert body["description"] == "Product engineers"
    assert "created_at" in body
    assert "updated_at" in body


def test_admin_can_list_teams(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    create_test_team(db_session, name="Engineering")
    create_test_team(db_session, name="Operations")

    response = client.get("/admin/teams", headers=bearer_header(admin))

    assert response.status_code == 200
    assert [team["name"] for team in response.json()] == ["Engineering", "Operations"]


def test_admin_can_list_teams_with_pagination(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    create_test_team(db_session, name="Engineering")
    create_test_team(db_session, name="Operations")
    create_test_team(db_session, name="Sales")

    response = client.get("/admin/teams?skip=1&limit=1", headers=bearer_header(admin))

    assert response.status_code == 200
    assert [team["name"] for team in response.json()] == ["Operations"]


def test_admin_can_get_team_by_id(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    team = create_test_team(db_session, name="Engineering")

    response = client.get(f"/admin/teams/{team.id}", headers=bearer_header(admin))

    assert response.status_code == 200
    assert response.json()["name"] == "Engineering"


def test_get_missing_team_returns_404(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)

    response = client.get("/admin/teams/999", headers=bearer_header(admin))

    assert response.status_code == 404
    assert response.json() == {"detail": "Team not found"}


def test_admin_can_update_team(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    team = create_test_team(db_session, name="Engineering", description="Old")

    response = client.patch(
        f"/admin/teams/{team.id}",
        json={"name": "Platform", "description": None},
        headers=bearer_header(admin),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Platform"
    assert body["description"] is None


def test_update_missing_team_returns_404(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)

    response = client.patch(
        "/admin/teams/999",
        json={"name": "Platform"},
        headers=bearer_header(admin),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Team not found"}


def test_update_team_with_null_name_returns_422(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    team = create_test_team(db_session, name="Engineering")

    response = client.patch(
        f"/admin/teams/{team.id}",
        json={"name": None},
        headers=bearer_header(admin),
    )

    assert response.status_code == 422


def test_admin_can_delete_team(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    team = create_test_team(db_session, name="Engineering")

    response = client.delete(f"/admin/teams/{team.id}", headers=bearer_header(admin))

    assert response.status_code == 204
    assert response.content == b""
    assert TeamRepository(db_session).get_by_id(team.id) is None


def test_delete_missing_team_returns_404(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)

    response = client.delete("/admin/teams/999", headers=bearer_header(admin))

    assert response.status_code == 404
    assert response.json() == {"detail": "Team not found"}


def test_create_duplicate_team_name_returns_409(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    create_test_team(db_session, name="Engineering")

    response = client.post(
        "/admin/teams",
        json={"name": "Engineering"},
        headers=bearer_header(admin),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Team name already exists"}


def test_update_duplicate_team_name_returns_409(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    create_test_team(db_session, name="Engineering")
    team = create_test_team(db_session, name="Operations")

    response = client.patch(
        f"/admin/teams/{team.id}",
        json={"name": "Engineering"},
        headers=bearer_header(admin),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Team name already exists"}


def test_employee_cannot_access_admin_team_routes(client: TestClient, db_session: Session) -> None:
    employee = create_test_user(
        db_session,
        email="employee@example.com",
        username="employee",
        role=UserRole.EMPLOYEE,
    )

    response = client.get("/admin/teams", headers=bearer_header(employee))

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}


def test_parking_owner_cannot_access_admin_team_routes(client: TestClient, db_session: Session) -> None:
    parking_owner = create_test_user(
        db_session,
        email="owner@example.com",
        username="owner",
        role=UserRole.PARKING_OWNER,
    )

    response = client.get("/admin/teams", headers=bearer_header(parking_owner))

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}


def test_missing_token_returns_401(client: TestClient) -> None:
    response = client.get("/admin/teams")

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


def test_invalid_token_returns_401(client: TestClient) -> None:
    response = client.get("/admin/teams", headers={"Authorization": "Bearer invalid-token"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}
