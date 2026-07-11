from collections.abc import Generator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.config import get_settings
from app.core.security import decode_access_token, hash_password
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
    password: str = "valid-password",
    is_active: bool = True,
    role: UserRole = UserRole.EMPLOYEE,
) -> User:
    repository = UserRepository(db_session)
    user = repository.create(
        email=email,
        username=username,
        first_name="Ada",
        last_name="Lovelace",
        hashed_password=hash_password(password),
        role=role,
        is_active=is_active,
    )
    db_session.commit()
    return user


def test_login_with_username_returns_bearer_token(client: TestClient, db_session: Session) -> None:
    user = create_test_user(db_session, role=UserRole.ADMIN)

    response = client.post(
        "/auth/login",
        json={"identifier": "alovelace", "password": "valid-password"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"].count(".") == 2

    payload = decode_access_token(body["access_token"], settings=get_settings())
    assert payload is not None
    assert payload.sub == str(user.id)
    assert payload.role is UserRole.ADMIN


def test_login_with_email_returns_bearer_token(client: TestClient, db_session: Session) -> None:
    user = create_test_user(db_session, role=UserRole.PARKING_OWNER)

    response = client.post(
        "/auth/login",
        json={"identifier": "ada.lovelace@example.com", "password": "valid-password"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"

    payload = decode_access_token(body["access_token"], settings=get_settings())
    assert payload is not None
    assert payload.sub == str(user.id)
    assert payload.role is UserRole.PARKING_OWNER


def test_oauth2_token_form_with_username_returns_bearer_token(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_test_user(db_session, role=UserRole.ADMIN)

    response = client.post(
        "/auth/token",
        data={"username": "alovelace", "password": "valid-password"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"

    payload = decode_access_token(body["access_token"], settings=get_settings())
    assert payload is not None
    assert payload.sub == str(user.id)
    assert payload.role is UserRole.ADMIN


def test_oauth2_token_form_with_email_returns_bearer_token(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_test_user(db_session, role=UserRole.PARKING_OWNER)

    response = client.post(
        "/auth/token",
        data={"username": "ada.lovelace@example.com", "password": "valid-password"},
    )

    assert response.status_code == 200
    payload = decode_access_token(response.json()["access_token"], settings=get_settings())
    assert payload is not None
    assert payload.sub == str(user.id)
    assert payload.role is UserRole.PARKING_OWNER


def test_login_wrong_password_returns_401(client: TestClient, db_session: Session) -> None:
    create_test_user(db_session)

    response = client.post(
        "/auth/login",
        json={"identifier": "alovelace", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}


def test_oauth2_token_form_wrong_password_returns_401(
    client: TestClient,
    db_session: Session,
) -> None:
    create_test_user(db_session)

    response = client.post(
        "/auth/token",
        data={"username": "alovelace", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}


def test_login_unknown_identifier_returns_401_without_printing_credentials(
    client: TestClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    response = client.post(
        "/auth/login",
        json={"identifier": "unknown", "password": "valid-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}
    captured = capsys.readouterr()
    assert "valid-password" not in captured.out
    assert "valid-password" not in captured.err


def test_login_inactive_user_returns_401(client: TestClient, db_session: Session) -> None:
    create_test_user(db_session, is_active=False)

    response = client.post(
        "/auth/login",
        json={"identifier": "alovelace", "password": "valid-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}


def test_login_response_does_not_contain_password_hash(client: TestClient, db_session: Session) -> None:
    create_test_user(db_session)

    response = client.post(
        "/auth/login",
        json={"identifier": "alovelace", "password": "valid-password"},
    )

    body = response.json()
    assert response.status_code == 200
    assert "hashed_password" not in body
    assert "password" not in body

    raw_payload = jwt.decode(
        body["access_token"],
        get_settings().jwt_secret_key,
        algorithms=[get_settings().jwt_algorithm],
    )
    assert "hashed_password" not in raw_payload
    assert "password" not in raw_payload


def test_auth_login_route_is_listed_in_openapi(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/auth/login" in response.json()["paths"]


def test_openapi_oauth2_password_flow_uses_form_token_endpoint(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    security_scheme = response.json()["components"]["securitySchemes"]["OAuth2PasswordBearer"]
    assert security_scheme["flows"]["password"]["tokenUrl"] == "/auth/token"
    assert "/auth/token" in response.json()["paths"]
