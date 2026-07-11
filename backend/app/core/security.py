from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.models.user import UserRole
from app.schemas.auth import TokenPayload


password_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__truncate_error=True)


def hash_password(plain_password: str) -> str:
    return password_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_context.verify(plain_password, hashed_password)


def create_access_token(
    subject: str | int,
    role: UserRole | str,
    expires_delta: timedelta | None = None,
    settings: Settings | None = None,
) -> str:
    resolved_settings = settings or get_settings()
    issued_at = datetime.now(UTC)
    token_lifetime = (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=resolved_settings.access_token_expire_minutes)
    )
    expires_at = issued_at + token_lifetime
    role_value = role.value if isinstance(role, UserRole) else role

    payload = {
        "sub": str(subject),
        "role": role_value,
        "iat": issued_at,
        "exp": expires_at,
    }
    return jwt.encode(
        payload,
        resolved_settings.jwt_secret_key,
        algorithm=resolved_settings.jwt_algorithm,
    )


def decode_access_token(token: str, settings: Settings | None = None) -> TokenPayload | None:
    """Return a validated token payload, or None for invalid/expired tokens."""
    resolved_settings = settings or get_settings()

    try:
        payload = jwt.decode(
            token,
            resolved_settings.jwt_secret_key,
            algorithms=[resolved_settings.jwt_algorithm],
        )
        return TokenPayload.model_validate(payload)
    except (JWTError, ValidationError):
        return None
