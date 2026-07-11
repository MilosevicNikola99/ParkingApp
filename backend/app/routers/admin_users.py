from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import get_db
from app.dependencies import require_admin
from app.models.user import User
from app.repositories.teams import TeamRepository
from app.repositories.users import UserRepository
from app.schemas.user import UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


def get_user_repository(db: Annotated[Session, Depends(get_db)]) -> UserRepository:
    return UserRepository(db)


def get_team_repository(db: Annotated[Session, Depends(get_db)]) -> TeamRepository:
    return TeamRepository(db)


def user_not_found_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


def team_not_found_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")


def duplicate_email_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")


def duplicate_username_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")


def duplicate_user_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="User email or username already exists",
    )


def user_delete_conflict_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User cannot be deleted")


def self_delete_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Admins cannot delete their own account",
    )


def ensure_team_exists(repository: TeamRepository, team_id: int | None) -> None:
    if team_id is not None and repository.get_by_id(team_id) is None:
        raise team_not_found_exception()


def ensure_email_available(
    repository: UserRepository,
    *,
    email: str,
    current_user_id: int | None = None,
) -> None:
    existing_user = repository.get_by_email(email)
    if existing_user is not None and existing_user.id != current_user_id:
        raise duplicate_email_exception()


def ensure_username_available(
    repository: UserRepository,
    *,
    username: str,
    current_user_id: int | None = None,
) -> None:
    existing_user = repository.get_by_username(username)
    if existing_user is not None and existing_user.id != current_user_id:
        raise duplicate_username_exception()


@router.get("", response_model=list[UserRead])
def list_users(
    _current_admin: Annotated[User, Depends(require_admin)],
    repository: Annotated[UserRepository, Depends(get_user_repository)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    team_id: Annotated[int | None, Query(ge=1)] = None,
) -> list[User]:
    if team_id is not None:
        return repository.list_by_team_id(team_id, skip=skip, limit=limit)

    return repository.list(skip=skip, limit=limit)


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: int,
    _current_admin: Annotated[User, Depends(require_admin)],
    repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> User:
    user = repository.get_by_id(user_id)
    if user is None:
        raise user_not_found_exception()

    return user


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    user_create: UserCreate,
    _current_admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
    team_repository: Annotated[TeamRepository, Depends(get_team_repository)],
) -> User:
    ensure_team_exists(team_repository, user_create.team_id)
    ensure_email_available(user_repository, email=str(user_create.email))
    ensure_username_available(user_repository, username=user_create.username)

    try:
        user = user_repository.create(
            email=str(user_create.email),
            username=user_create.username,
            first_name=user_create.first_name,
            last_name=user_create.last_name,
            hashed_password=hash_password(user_create.password),
            role=user_create.role,
            team_id=user_create.team_id,
            is_active=user_create.is_active,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise duplicate_user_exception() from exc

    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    user_update: UserUpdate,
    _current_admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
    team_repository: Annotated[TeamRepository, Depends(get_team_repository)],
) -> User:
    user = user_repository.get_by_id(user_id)
    if user is None:
        raise user_not_found_exception()

    updates = user_update.model_dump(exclude_unset=True)
    if "team_id" in updates:
        ensure_team_exists(team_repository, updates["team_id"])
    if "email" in updates:
        updates["email"] = str(updates["email"])
        ensure_email_available(user_repository, email=updates["email"], current_user_id=user.id)
    if "username" in updates:
        ensure_username_available(
            user_repository,
            username=updates["username"],
            current_user_id=user.id,
        )
    if "password" in updates:
        updates["hashed_password"] = hash_password(updates.pop("password"))

    if not updates:
        return user

    try:
        user = user_repository.update(user, updates)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise duplicate_user_exception() from exc

    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    current_admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> Response:
    user = repository.get_by_id(user_id)
    if user is None:
        raise user_not_found_exception()
    if user.id == current_admin.id:
        raise self_delete_exception()

    try:
        repository.delete(user)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise user_delete_conflict_exception() from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
