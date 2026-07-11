from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.metrics import record_auth_failure
from app.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories.users import UserRepository
from app.schemas.auth import LoginRequest, Token
from app.schemas.user import UserRead
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(user_repository=UserRepository(db))


def create_login_token(
    *,
    identifier: str,
    password: str,
    auth_service: AuthService,
) -> Token:
    user = auth_service.authenticate_user(identifier, password)
    if user is None:
        record_auth_failure("invalid_credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return auth_service.create_access_token_for_user(user)


@router.post(
    "/login",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "Invalid credentials"}},
)
def login(
    credentials: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> Token:
    return create_login_token(
        identifier=credentials.identifier,
        password=credentials.password,
        auth_service=auth_service,
    )


@router.post(
    "/token",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "Invalid credentials"}},
)
def login_with_oauth2_form(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    auth_service: AuthService = Depends(get_auth_service),
) -> Token:
    return create_login_token(
        identifier=form_data.username,
        password=form_data.password,
        auth_service=auth_service,
    )


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user
