from collections.abc import Generator
import importlib

from pydantic import ValidationError
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.commands import seed_admin as seed_admin_command
from app.core.config import Settings
from app.core.security import hash_password, verify_password
from app.db.base import Base
from app.models.user import User, UserRole
from app.repositories.users import UserRepository


@pytest.fixture()
def session_factory() -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    yield factory

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def db_session(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    with session_factory() as session:
        yield session


def enabled_seed_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "seed_admin_enabled": True,
        "seed_admin_email": "local.admin@example.com",
        "seed_admin_username": "local_admin",
        "seed_admin_password": "local-admin-password",
        "seed_admin_first_name": "Local",
        "seed_admin_last_name": "Admin",
    }
    values.update(overrides)
    return Settings(**values)


def test_seed_admin_module_is_import_safe(capsys: pytest.CaptureFixture[str]) -> None:
    importlib.reload(seed_admin_command)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_seed_admin_does_nothing_when_disabled(db_session: Session) -> None:
    result = seed_admin_command.seed_admin(db_session, Settings(seed_admin_enabled=False))

    assert result.action == "disabled"
    assert db_session.scalar(select(func.count(User.id))) == 0


def test_seed_admin_refuses_production_environment(db_session: Session) -> None:
    with pytest.raises(ValidationError, match="seed admin"):
        enabled_seed_settings(
            environment="production",
            jwt_secret_key="production-jwt-secret-with-at-least-32-characters",
            database_url="",
            database_password="production-database-password",
            cors_allowed_origins=["https://parking.example.com"],
        )

    assert db_session.scalar(select(func.count(User.id))) == 0


def test_seed_admin_refuses_other_non_development_environments(db_session: Session) -> None:
    settings = enabled_seed_settings(environment="staging")

    with pytest.raises(seed_admin_command.SeedAdminConfigurationError, match="outside"):
        seed_admin_command.seed_admin(db_session, settings)

    assert db_session.scalar(select(func.count(User.id))) == 0


def test_seed_admin_missing_required_variables_returns_clean_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    password = "not-printed-password"
    settings = Settings(
        seed_admin_enabled=True,
        seed_admin_password=password,
    )

    exit_code = seed_admin_command.main([], settings=settings)

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "missing required seed admin variables" in captured.err
    assert password not in captured.out
    assert password not in captured.err


def test_seed_admin_creates_active_admin_with_hashed_password(db_session: Session) -> None:
    settings = enabled_seed_settings()

    result = seed_admin_command.seed_admin(db_session, settings)
    created_user = UserRepository(db_session).get_by_username("local_admin")

    assert result == seed_admin_command.SeedAdminResult(
        action="created",
        username="local_admin",
        password_updated=True,
    )
    assert created_user is not None
    assert created_user.role is UserRole.ADMIN
    assert created_user.is_active is True
    assert created_user.hashed_password != "local-admin-password"
    assert verify_password("local-admin-password", created_user.hashed_password) is True


def test_seed_admin_preserves_existing_password_by_default(db_session: Session) -> None:
    original_hash = hash_password("original-password")
    repository = UserRepository(db_session)
    existing_user = repository.create(
        email="old.admin@example.com",
        username="local_admin",
        first_name="Old",
        last_name="Name",
        hashed_password=original_hash,
        role=UserRole.ADMIN,
        is_active=False,
    )
    db_session.commit()
    settings = enabled_seed_settings()

    result = seed_admin_command.seed_admin(db_session, settings)
    db_session.refresh(existing_user)

    assert result.action == "updated"
    assert result.password_updated is False
    assert existing_user.hashed_password == original_hash
    assert verify_password("local-admin-password", existing_user.hashed_password) is False
    assert existing_user.email == "local.admin@example.com"
    assert existing_user.first_name == "Local"
    assert existing_user.last_name == "Admin"
    assert existing_user.is_active is True


def test_seed_admin_updates_existing_password_only_when_enabled(db_session: Session) -> None:
    original_hash = hash_password("original-password")
    existing_user = UserRepository(db_session).create(
        email="local.admin@example.com",
        username="local_admin",
        first_name="Local",
        last_name="Admin",
        hashed_password=original_hash,
        role=UserRole.ADMIN,
    )
    db_session.commit()
    settings = enabled_seed_settings(seed_admin_update_password=True)

    result = seed_admin_command.seed_admin(db_session, settings)
    db_session.refresh(existing_user)

    assert result.password_updated is True
    assert existing_user.hashed_password != original_hash
    assert verify_password("local-admin-password", existing_user.hashed_password) is True


def test_seed_admin_repeated_run_is_idempotent(db_session: Session) -> None:
    settings = enabled_seed_settings()

    first_result = seed_admin_command.seed_admin(db_session, settings)
    first_user = UserRepository(db_session).get_by_username("local_admin")
    first_hash = first_user.hashed_password
    second_result = seed_admin_command.seed_admin(db_session, settings)

    assert first_result.action == "created"
    assert second_result.action == "updated"
    assert second_result.password_updated is False
    assert db_session.scalar(select(func.count(User.id))) == 1
    assert UserRepository(db_session).get_by_username("local_admin").hashed_password == first_hash


def test_seed_admin_refuses_email_username_collision(db_session: Session) -> None:
    repository = UserRepository(db_session)
    repository.create(
        email="local.admin@example.com",
        username="first_admin",
        first_name="First",
        last_name="Admin",
        hashed_password=hash_password("first-password"),
        role=UserRole.ADMIN,
    )
    repository.create(
        email="second.admin@example.com",
        username="local_admin",
        first_name="Second",
        last_name="Admin",
        hashed_password=hash_password("second-password"),
        role=UserRole.ADMIN,
    )
    db_session.commit()

    with pytest.raises(seed_admin_command.SeedAdminConfigurationError, match="different users"):
        seed_admin_command.seed_admin(db_session, enabled_seed_settings())

    assert db_session.scalar(select(func.count(User.id))) == 2


def test_seed_admin_command_output_excludes_password_and_hash(
    session_factory: sessionmaker[Session],
    capsys: pytest.CaptureFixture[str],
) -> None:
    password = "command-output-password"
    settings = enabled_seed_settings(seed_admin_password=password)

    exit_code = seed_admin_command.main(
        [],
        settings=settings,
        session_factory=session_factory,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "seed admin created: username=local_admin password=updated" in captured.out
    assert password not in captured.out
    assert password not in captured.err
    assert "$2b$" not in captured.out
    assert "$2b$" not in captured.err


def test_seed_admin_command_disabled_exits_cleanly(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = seed_admin_command.main([], settings=Settings(seed_admin_enabled=False))

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "seed admin disabled; no changes made"
    assert captured.err == ""
