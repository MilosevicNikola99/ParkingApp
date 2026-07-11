from datetime import timedelta

from app.core.config import Settings
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.models.user import UserRole


TEST_SETTINGS = Settings(
    jwt_secret_key="test-secret-key",
    jwt_algorithm="HS256",
    access_token_expire_minutes=15,
)


def test_hash_password_returns_non_plaintext_hash() -> None:
    plain_password = "correct-horse-battery-staple"

    hashed_password = hash_password(plain_password)

    assert hashed_password != plain_password
    assert plain_password not in hashed_password


def test_verify_password_accepts_correct_password() -> None:
    plain_password = "correct-horse-battery-staple"
    hashed_password = hash_password(plain_password)

    assert verify_password(plain_password, hashed_password) is True


def test_verify_password_rejects_wrong_password() -> None:
    hashed_password = hash_password("correct-horse-battery-staple")

    assert verify_password("wrong-password", hashed_password) is False


def test_create_access_token_returns_string() -> None:
    token = create_access_token(subject=42, role=UserRole.ADMIN, settings=TEST_SETTINGS)

    assert isinstance(token, str)
    assert token.count(".") == 2


def test_decode_access_token_returns_expected_payload() -> None:
    token = create_access_token(subject=42, role=UserRole.ADMIN, settings=TEST_SETTINGS)

    payload = decode_access_token(token, settings=TEST_SETTINGS)

    assert payload is not None
    assert payload.sub == "42"
    assert payload.role is UserRole.ADMIN
    assert payload.exp.tzinfo is not None


def test_decode_access_token_rejects_expired_token() -> None:
    token = create_access_token(
        subject=42,
        role=UserRole.EMPLOYEE,
        expires_delta=timedelta(minutes=-1),
        settings=TEST_SETTINGS,
    )

    assert decode_access_token(token, settings=TEST_SETTINGS) is None


def test_decode_access_token_rejects_invalid_token() -> None:
    assert decode_access_token("not-a-valid-jwt", settings=TEST_SETTINGS) is None
