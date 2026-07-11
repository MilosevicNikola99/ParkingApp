from collections.abc import Generator

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.dependencies.auth import require_admin, require_roles
from app.main import create_app
from app.models.user import User, UserRole
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
def app_with_role_routes(db_session: Session) -> Generator[FastAPI, None, None]:
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    @app.get("/test/admin-only")
    def admin_only(current_user: User = Depends(require_admin)) -> dict[str, str | int]:
        return {"id": current_user.id, "role": current_user.role.value}

    @app.get("/test/employee-or-owner")
    def employee_or_owner(
        current_user: User = Depends(require_roles(UserRole.EMPLOYEE, UserRole.PARKING_OWNER)),
    ) -> dict[str, str | int]:
        return {"id": current_user.id, "role": current_user.role.value}

    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture()
def client(app_with_role_routes: FastAPI) -> TestClient:
    return TestClient(app_with_role_routes)


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


def bearer_header(user: User) -> dict[str, str]:
    token = create_access_token(subject=user.id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


def test_admin_user_passes_require_admin(client: TestClient, db_session: Session) -> None:
    user = create_test_user(
        db_session,
        email="admin@example.com",
        username="admin",
        role=UserRole.ADMIN,
    )

    response = client.get("/test/admin-only", headers=bearer_header(user))

    assert response.status_code == 200
    assert response.json() == {"id": user.id, "role": "admin"}


def test_employee_user_fails_require_admin_with_403(client: TestClient, db_session: Session) -> None:
    user = create_test_user(
        db_session,
        email="employee@example.com",
        username="employee",
        role=UserRole.EMPLOYEE,
    )

    response = client.get("/test/admin-only", headers=bearer_header(user))

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}


def test_parking_owner_user_fails_require_admin_with_403(client: TestClient, db_session: Session) -> None:
    user = create_test_user(
        db_session,
        email="owner@example.com",
        username="owner",
        role=UserRole.PARKING_OWNER,
    )

    response = client.get("/test/admin-only", headers=bearer_header(user))

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}


def test_require_roles_allows_one_of_multiple_roles(client: TestClient, db_session: Session) -> None:
    user = create_test_user(
        db_session,
        email="owner@example.com",
        username="owner",
        role=UserRole.PARKING_OWNER,
    )

    response = client.get("/test/employee-or-owner", headers=bearer_header(user))

    assert response.status_code == 200
    assert response.json() == {"id": user.id, "role": "parking_owner"}


def test_require_roles_rejects_role_not_in_permitted_set(client: TestClient, db_session: Session) -> None:
    user = create_test_user(
        db_session,
        email="admin@example.com",
        username="admin",
        role=UserRole.ADMIN,
    )

    response = client.get("/test/employee-or-owner", headers=bearer_header(user))

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}


def test_missing_token_still_returns_401_through_get_current_user(client: TestClient) -> None:
    response = client.get("/test/admin-only")

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


def test_invalid_token_still_returns_401_through_get_current_user(client: TestClient) -> None:
    response = client.get("/test/admin-only", headers={"Authorization": "Bearer invalid-token"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


def test_inactive_user_still_returns_401_through_get_current_user(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_test_user(
        db_session,
        email="inactive@example.com",
        username="inactive",
        role=UserRole.ADMIN,
        is_active=False,
    )

    response = client.get("/test/admin-only", headers=bearer_header(user))

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


def test_role_dependency_route_keeps_bearer_security_in_openapi(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    operation = response.json()["paths"]["/test/admin-only"]["get"]
    assert operation["security"] == [{"OAuth2PasswordBearer": []}]
