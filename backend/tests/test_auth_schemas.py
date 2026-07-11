from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.models.user import UserRole
from app.schemas.auth import LoginRequest, Token, TokenPayload


def test_token_schema_defaults_to_bearer_type() -> None:
    token = Token(access_token="abc.def.ghi")

    assert token.model_dump() == {
        "access_token": "abc.def.ghi",
        "token_type": "bearer",
    }


def test_token_payload_schema_validates_role_and_timestamps() -> None:
    expires_at = datetime.now(UTC) + timedelta(minutes=15)

    payload = TokenPayload(sub="123", role="employee", exp=expires_at)

    dumped = payload.model_dump(mode="json")

    assert dumped["sub"] == "123"
    assert payload.role is UserRole.EMPLOYEE
    assert dumped["role"] == "employee"
    assert "exp" in dumped


def test_token_payload_rejects_missing_subject() -> None:
    with pytest.raises(ValidationError):
        TokenPayload(role="employee", exp=datetime.now(UTC))


def test_login_request_accepts_identifier_and_password() -> None:
    request = LoginRequest(identifier="alovelace", password="plain-password")

    assert request.identifier == "alovelace"
    assert request.password == "plain-password"


def test_login_request_accepts_email_alias() -> None:
    request = LoginRequest(email="ada.lovelace@example.com", password="plain-password")

    assert request.identifier == "ada.lovelace@example.com"


def test_login_request_accepts_username_alias() -> None:
    request = LoginRequest(username="alovelace", password="plain-password")

    assert request.identifier == "alovelace"


def test_login_request_rejects_blank_identifier() -> None:
    with pytest.raises(ValidationError):
        LoginRequest(identifier="", password="plain-password")


def test_login_request_rejects_password_over_bcrypt_limit() -> None:
    with pytest.raises(ValidationError):
        LoginRequest(identifier="ada.lovelace@example.com", password="a" * 73)
