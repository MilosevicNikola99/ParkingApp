from app.core.config import Settings, get_settings
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.repositories.users import UserRepository
from app.schemas.auth import Token


class AuthService:
    def __init__(self, user_repository: UserRepository, settings: Settings | None = None) -> None:
        self.user_repository = user_repository
        self.settings = settings or get_settings()

    def authenticate_user(self, identifier: str, plain_password: str) -> User | None:
        """Return the active user for valid credentials, otherwise None."""
        normalized_identifier = identifier.strip()
        if not normalized_identifier:
            return None

        user = self._get_user_by_identifier(normalized_identifier)
        if user is None:
            return None
        if not user.is_active:
            return None
        if not verify_password(plain_password, user.hashed_password):
            return None

        return user

    def create_access_token_for_user(self, user: User) -> Token:
        access_token = create_access_token(
            subject=user.id,
            role=user.role,
            settings=self.settings,
        )
        return Token(access_token=access_token)

    def _get_user_by_identifier(self, identifier: str) -> User | None:
        if "@" in identifier:
            return self.user_repository.get_by_email(identifier) or self.user_repository.get_by_username(
                identifier
            )

        return self.user_repository.get_by_username(identifier) or self.user_repository.get_by_email(identifier)
