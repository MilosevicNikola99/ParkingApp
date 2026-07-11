from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from dataclasses import dataclass
import sys
from typing import Literal

from pydantic import SecretStr, ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.repositories.users import UserRepository
from app.schemas.user import UserCreate


class SeedAdminConfigurationError(ValueError):
    """Raised when local admin seed configuration is unsafe or incomplete."""


@dataclass(frozen=True)
class SeedAdminResult:
    action: Literal["disabled", "created", "updated"]
    username: str | None = None
    password_updated: bool = False


SessionFactory = Callable[[], Session]


def validate_seed_admin_settings(settings: Settings) -> UserCreate | None:
    if not settings.seed_admin_enabled:
        return None
    allowed_environments = {"local", "development", "dev", "test"}
    if settings.environment.lower() not in allowed_environments:
        raise SeedAdminConfigurationError(
            "refusing to seed an admin outside local/development/test environments",
        )

    required_values = {
        "SEED_ADMIN_EMAIL": settings.seed_admin_email,
        "SEED_ADMIN_USERNAME": settings.seed_admin_username,
        "SEED_ADMIN_PASSWORD": settings.seed_admin_password,
        "SEED_ADMIN_FIRST_NAME": settings.seed_admin_first_name,
        "SEED_ADMIN_LAST_NAME": settings.seed_admin_last_name,
    }
    missing_fields = sorted(
        field_name
        for field_name, value in required_values.items()
        if (
            value is None
            or (isinstance(value, str) and not value.strip())
            or (isinstance(value, SecretStr) and not value.get_secret_value().strip())
        )
    )
    if missing_fields:
        raise SeedAdminConfigurationError(
            f"missing required seed admin variables: {', '.join(missing_fields)}",
        )

    try:
        return UserCreate(
            email=settings.seed_admin_email,
            username=settings.seed_admin_username,
            password=settings.seed_admin_password.get_secret_value(),
            first_name=settings.seed_admin_first_name,
            last_name=settings.seed_admin_last_name,
            role=UserRole.ADMIN,
            is_active=True,
        )
    except ValidationError as exc:
        invalid_fields = sorted({str(error["loc"][0]).upper() for error in exc.errors()})
        raise SeedAdminConfigurationError(
            f"invalid seed admin fields: {', '.join(invalid_fields)}",
        ) from exc


def resolve_existing_user(repository: UserRepository, seed_user: UserCreate) -> User | None:
    user_by_email = repository.get_by_email(str(seed_user.email))
    user_by_username = repository.get_by_username(seed_user.username)
    if (
        user_by_email is not None
        and user_by_username is not None
        and user_by_email.id != user_by_username.id
    ):
        raise SeedAdminConfigurationError(
            "seed admin email and username belong to different users",
        )

    return user_by_email or user_by_username


def seed_admin(db: Session, settings: Settings) -> SeedAdminResult:
    seed_user = validate_seed_admin_settings(settings)
    if seed_user is None:
        return SeedAdminResult(action="disabled")

    repository = UserRepository(db)
    try:
        existing_user = resolve_existing_user(repository, seed_user)
        if existing_user is None:
            repository.create(
                email=str(seed_user.email),
                username=seed_user.username,
                first_name=seed_user.first_name,
                last_name=seed_user.last_name,
                hashed_password=hash_password(seed_user.password),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.commit()
            return SeedAdminResult(
                action="created",
                username=seed_user.username,
                password_updated=True,
            )

        updates: dict[str, object] = {
            "email": str(seed_user.email),
            "username": seed_user.username,
            "first_name": seed_user.first_name,
            "last_name": seed_user.last_name,
            "role": UserRole.ADMIN,
            "is_active": True,
        }
        if settings.seed_admin_update_password:
            updates["hashed_password"] = hash_password(seed_user.password)

        repository.update(existing_user, updates)
        db.commit()
        return SeedAdminResult(
            action="updated",
            username=seed_user.username,
            password_updated=settings.seed_admin_update_password,
        )
    except Exception:
        db.rollback()
        raise


def run_seed_admin(
    *,
    settings: Settings | None = None,
    session_factory: SessionFactory | None = None,
) -> SeedAdminResult:
    resolved_settings = settings or get_settings()
    seed_user = validate_seed_admin_settings(resolved_settings)
    if seed_user is None:
        return SeedAdminResult(action="disabled")

    if session_factory is None:
        from app.db.session import SessionLocal

        session_factory = SessionLocal

    with session_factory() as db:
        return seed_admin(db, resolved_settings)


def format_result(result: SeedAdminResult) -> str:
    if result.action == "disabled":
        return "seed admin disabled; no changes made"

    password_status = "updated" if result.password_updated else "preserved"
    return (
        f"seed admin {result.action}: username={result.username} "
        f"password={password_status}"
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
    session_factory: SessionFactory | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="Create or update a local development admin.")
    parser.parse_args(argv)

    try:
        result = run_seed_admin(settings=settings, session_factory=session_factory)
    except SeedAdminConfigurationError as exc:
        print(f"seed admin failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"seed admin failed: {type(exc).__name__}", file=sys.stderr)
        return 1

    print(format_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
