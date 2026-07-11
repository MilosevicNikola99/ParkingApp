from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import require_admin
from app.models.team import Team
from app.repositories.teams import TeamRepository
from app.schemas.team import TeamCreate, TeamRead, TeamUpdate

router = APIRouter(
    prefix="/admin/teams",
    tags=["admin-teams"],
    dependencies=[Depends(require_admin)],
)


def get_team_repository(db: Annotated[Session, Depends(get_db)]) -> TeamRepository:
    return TeamRepository(db)


def team_not_found_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")


def duplicate_team_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Team name already exists",
    )


def team_delete_conflict_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Team cannot be deleted",
    )


def ensure_team_name_available(
    repository: TeamRepository,
    *,
    name: str,
    current_team_id: int | None = None,
) -> None:
    existing_team = repository.get_by_name(name)
    if existing_team is not None and existing_team.id != current_team_id:
        raise duplicate_team_exception()


@router.get("", response_model=list[TeamRead])
def list_teams(
    repository: Annotated[TeamRepository, Depends(get_team_repository)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> list[Team]:
    return repository.list(skip=skip, limit=limit)


@router.get("/{team_id}", response_model=TeamRead)
def get_team(
    team_id: int,
    repository: Annotated[TeamRepository, Depends(get_team_repository)],
) -> Team:
    team = repository.get_by_id(team_id)
    if team is None:
        raise team_not_found_exception()

    return team


@router.post("", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
def create_team(
    team_create: TeamCreate,
    db: Annotated[Session, Depends(get_db)],
    repository: Annotated[TeamRepository, Depends(get_team_repository)],
) -> Team:
    ensure_team_name_available(repository, name=team_create.name)

    try:
        team = repository.create(
            name=team_create.name,
            description=team_create.description,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise duplicate_team_exception() from exc

    db.refresh(team)
    return team


@router.patch("/{team_id}", response_model=TeamRead)
def update_team(
    team_id: int,
    team_update: TeamUpdate,
    db: Annotated[Session, Depends(get_db)],
    repository: Annotated[TeamRepository, Depends(get_team_repository)],
) -> Team:
    team = repository.get_by_id(team_id)
    if team is None:
        raise team_not_found_exception()

    updates = team_update.model_dump(exclude_unset=True)
    if "name" in updates:
        ensure_team_name_available(
            repository,
            name=updates["name"],
            current_team_id=team.id,
        )

    if not updates:
        return team

    try:
        team = repository.update(team, updates)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise duplicate_team_exception() from exc

    db.refresh(team)
    return team


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(
    team_id: int,
    db: Annotated[Session, Depends(get_db)],
    repository: Annotated[TeamRepository, Depends(get_team_repository)],
) -> Response:
    team = repository.get_by_id(team_id)
    if team is None:
        raise team_not_found_exception()

    try:
        repository.delete(team)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise team_delete_conflict_exception() from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
