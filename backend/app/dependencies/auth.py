from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User, UserRole
from app.repositories.users import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


def credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def permissions_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not enough permissions",
    )


def get_current_user(
    token: Annotated[str | None, Security(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if token is None:
        raise credentials_exception()

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception()

    try:
        user_id = int(payload.sub)
    except ValueError as exc:
        raise credentials_exception() from exc

    user = UserRepository(db).get_by_id(user_id)
    if user is None:
        raise credentials_exception()
    if not user.is_active:
        raise credentials_exception()

    return user


def require_roles(*allowed_roles: UserRole) -> Callable[[User], User]:
    allowed_role_set = set(allowed_roles)

    def dependency(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if current_user.role not in allowed_role_set:
            raise permissions_exception()

        return current_user

    return dependency


def require_admin(current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))]) -> User:
    return current_user
