from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.user import User, UserRole


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        email: str,
        username: str,
        first_name: str,
        last_name: str,
        hashed_password: str,
        role: UserRole = UserRole.EMPLOYEE,
        team_id: int | None = None,
        is_active: bool = True,
    ) -> User:
        user = User(
            email=email,
            username=username,
            first_name=first_name,
            last_name=last_name,
            hashed_password=hashed_password,
            role=role,
            team_id=team_id,
            is_active=is_active,
        )
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    def get_by_id(self, user_id: int) -> User | None:
        statement = (
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.team))
            .execution_options(populate_existing=True)
        )
        return self.db.execute(statement).scalar_one_or_none()

    def get_by_email(self, email: str) -> User | None:
        statement = (
            select(User)
            .where(User.email == email)
            .options(selectinload(User.team))
        )
        return self.db.execute(statement).scalar_one_or_none()

    def get_by_username(self, username: str) -> User | None:
        statement = (
            select(User)
            .where(User.username == username)
            .options(selectinload(User.team))
        )
        return self.db.execute(statement).scalar_one_or_none()

    def list(self, *, skip: int = 0, limit: int = 100) -> list[User]:
        statement = (
            select(User)
            .order_by(User.id)
            .offset(skip)
            .limit(limit)
            .options(selectinload(User.team))
        )
        return list(self.db.execute(statement).scalars().all())

    def list_by_team_id(self, team_id: int, *, skip: int = 0, limit: int = 100) -> list[User]:
        statement = (
            select(User)
            .where(User.team_id == team_id)
            .order_by(User.id)
            .offset(skip)
            .limit(limit)
            .options(selectinload(User.team))
        )
        return list(self.db.execute(statement).scalars().all())

    def update(self, user: User, updates: Mapping[str, Any]) -> User:
        allowed_fields = {
            "email",
            "username",
            "first_name",
            "last_name",
            "hashed_password",
            "role",
            "team_id",
            "is_active",
        }

        for field, value in updates.items():
            if field in allowed_fields:
                setattr(user, field, value)

        self.db.flush()
        self.db.refresh(user)
        return user

    def delete(self, user: User) -> bool:
        self.db.delete(user)
        self.db.flush()
        return True
