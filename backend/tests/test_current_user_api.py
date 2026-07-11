from collections.abc import Generator
from datetime import timedelta

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
    email: str = "ada.lovelace@example.com",
    username: str = "alovelace",
    is_active: bool = True,
    role: UserRole = UserRole.EMPLOYEE,
) -> User:
    repository = UserRepository(db_session)
    user = repository.create(
        email=email,
        username=username,
        first_name="Ada",
        last_name="Lovelace",
        hashed_password=hash_password("valid-password"),
        role=role,
        is_active=is_active,
    )
    db_session.commit()
    return user


def bearer_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_auth_me_with_valid_token_returns_current_user(client: TestClient, db_session: Session) -> None:
    user = create_test_user(db_session, role=UserRole.ADMIN)
    token = create_access_token(subject=user.id, role=user.role)

    response = client.get("/auth/me", headers=bearer_header(token))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == user.id
    assert body["email"] == "ada.lovelace@example.com"
    assert body["username"] == "alovelace"
    assert body["role"] == "admin"


def test_auth_me_response_does_not_contain_hashed_password(client: TestClient, db_session: Session) -> None:
    user = create_test_user(db_session)
    token = create_access_token(subject=user.id, role=user.role)

    response = client.get("/auth/me", headers=bearer_header(token))

    assert response.status_code == 200
    body = response.json()
    assert "hashed_password" not in body
    assert "password" not in body


def test_auth_me_missing_token_returns_401(client: TestClient) -> None:
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


def test_auth_me_malformed_token_returns_401(client: TestClient) -> None:
    response = client.get("/auth/me", headers=bearer_header("not-a-valid-jwt"))

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


def test_auth_me_expired_token_returns_401(client: TestClient, db_session: Session) -> None:
    user = create_test_user(db_session)
    token = create_access_token(
        subject=user.id,
        role=user.role,
        expires_delta=timedelta(minutes=-1),
    )

    response = client.get("/auth/me", headers=bearer_header(token))

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


def test_auth_me_token_for_missing_user_returns_401(client: TestClient) -> None:
    token = create_access_token(subject=999, role=UserRole.EMPLOYEE)

    response = client.get("/auth/me", headers=bearer_header(token))

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


def test_auth_me_token_for_inactive_user_returns_401(client: TestClient, db_session: Session) -> None:
    user = create_test_user(db_session, is_active=False)
    token = create_access_token(subject=user.id, role=user.role)

    response = client.get("/auth/me", headers=bearer_header(token))

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


def test_auth_me_token_with_non_integer_subject_returns_401(client: TestClient) -> None:
    token = create_access_token(subject="not-a-user-id", role=UserRole.EMPLOYEE)

    response = client.get("/auth/me", headers=bearer_header(token))

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


def test_auth_me_route_is_listed_with_security_in_openapi(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    operation = response.json()["paths"]["/auth/me"]["get"]
    assert operation["security"] == [{"OAuth2PasswordBearer": []}]
