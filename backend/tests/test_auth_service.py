from collections.abc import Generator

import jwt
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.core.config import Settings
from app.core.security import decode_access_token, hash_password
from app.db.base import Base
from app.models.user import User, UserRole
from app.repositories.users import UserRepository
from app.services.auth import AuthService


TEST_SETTINGS = Settings(
    jwt_secret_key="auth-service-test-secret-at-least-32-characters",
    jwt_algorithm="HS256",
    access_token_expire_minutes=15,
)


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def user_repository(db_session: Session) -> UserRepository:
    return UserRepository(db_session)


@pytest.fixture()
def auth_service(user_repository: UserRepository) -> AuthService:
    return AuthService(user_repository=user_repository, settings=TEST_SETTINGS)


def create_test_user(
    user_repository: UserRepository,
    *,
    email: str = "ada.lovelace@example.com",
    username: str = "alovelace",
    password: str = "valid-password",
    is_active: bool = True,
    role: UserRole = UserRole.EMPLOYEE,
) -> User:
    return user_repository.create(
        email=email,
        username=username,
        first_name="Ada",
        last_name="Lovelace",
        hashed_password=hash_password(password),
        role=role,
        is_active=is_active,
    )


def test_authenticates_active_user_with_username_and_correct_password(
    auth_service: AuthService,
    user_repository: UserRepository,
) -> None:
    user = create_test_user(user_repository)

    authenticated = auth_service.authenticate_user("alovelace", "valid-password")

    assert authenticated is user


def test_authenticates_active_user_with_email_and_correct_password(
    auth_service: AuthService,
    user_repository: UserRepository,
) -> None:
    user = create_test_user(user_repository)

    authenticated = auth_service.authenticate_user("ada.lovelace@example.com", "valid-password")

    assert authenticated is user


def test_authentication_fails_for_wrong_password(
    auth_service: AuthService,
    user_repository: UserRepository,
) -> None:
    create_test_user(user_repository)

    assert auth_service.authenticate_user("alovelace", "wrong-password") is None


def test_authentication_fails_for_unknown_identifier(auth_service: AuthService) -> None:
    assert auth_service.authenticate_user("unknown", "valid-password") is None


def test_authentication_fails_for_blank_identifier(auth_service: AuthService) -> None:
    assert auth_service.authenticate_user("   ", "valid-password") is None


def test_authentication_fails_for_inactive_user(
    auth_service: AuthService,
    user_repository: UserRepository,
) -> None:
    create_test_user(user_repository, is_active=False)

    assert auth_service.authenticate_user("alovelace", "valid-password") is None


def test_create_access_token_for_user_returns_token_schema(
    auth_service: AuthService,
    user_repository: UserRepository,
) -> None:
    user = create_test_user(user_repository, role=UserRole.ADMIN)

    token = auth_service.create_access_token_for_user(user)

    assert token.token_type == "bearer"
    assert token.access_token.count(".") == 2


def test_created_access_token_contains_expected_subject_and_role(
    auth_service: AuthService,
    user_repository: UserRepository,
) -> None:
    user = create_test_user(user_repository, role=UserRole.ADMIN)

    token = auth_service.create_access_token_for_user(user)
    payload = decode_access_token(token.access_token, settings=TEST_SETTINGS)

    assert payload is not None
    assert payload.sub == str(user.id)
    assert payload.role is UserRole.ADMIN


def test_created_access_token_does_not_expose_password_hash(
    auth_service: AuthService,
    user_repository: UserRepository,
) -> None:
    user = create_test_user(user_repository)

    token = auth_service.create_access_token_for_user(user)
    raw_payload = jwt.decode(
        token.access_token,
        TEST_SETTINGS.jwt_secret_key,
        algorithms=[TEST_SETTINGS.jwt_algorithm],
    )

    assert "hashed_password" not in raw_payload
    assert "password" not in raw_payload
