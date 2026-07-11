from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.team import Team


class TeamRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, *, name: str, description: str | None = None) -> Team:
        team = Team(name=name, description=description)
        self.db.add(team)
        self.db.flush()
        self.db.refresh(team)
        return team

    def get_by_id(self, team_id: int) -> Team | None:
        statement = (
            select(Team)
            .where(Team.id == team_id)
            .options(selectinload(Team.users))
            .execution_options(populate_existing=True)
        )
        return self.db.execute(statement).scalar_one_or_none()

    def get_by_name(self, name: str) -> Team | None:
        statement = (
            select(Team)
            .where(Team.name == name)
            .options(selectinload(Team.users))
        )
        return self.db.execute(statement).scalar_one_or_none()

    def list(self, *, skip: int = 0, limit: int = 100) -> list[Team]:
        statement = (
            select(Team)
            .order_by(Team.id)
            .offset(skip)
            .limit(limit)
            .options(selectinload(Team.users))
        )
        return list(self.db.execute(statement).scalars().all())

    def update(self, team: Team, updates: Mapping[str, Any]) -> Team:
        allowed_fields = {"name", "description"}

        for field, value in updates.items():
            if field in allowed_fields:
                setattr(team, field, value)

        self.db.flush()
        self.db.refresh(team)
        return team

    def delete(self, team: Team) -> bool:
        self.db.delete(team)
        self.db.flush()
        return True
