from pathlib import Path

from pydantic import ValidationError
import pytest

from app.core.config import (
    MIN_PRODUCTION_JWT_SECRET_LENGTH,
    Settings,
    build_database_url,
    is_local_environment,
    is_production_environment,
    normalize_environment,
)


VALID_PRODUCTION_JWT_SECRET = "prod-jwt-secret-value-with-at-least-32-chars"
VALID_PRODUCTION_DATABASE_PASSWORD = "prod-db-password-with-enough-entropy"


def write_secret(tmp_path: Path, name: str, value: str) -> Path:
    path = tmp_path / name
    path.write_text(value, encoding="utf-8")
    return path


def production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "production",
        "jwt_secret_key": VALID_PRODUCTION_JWT_SECRET,
        "database_url": "",
        "database_host": "db",
        "database_user": "parking_app_prod",
        "database_password": VALID_PRODUCTION_DATABASE_PASSWORD,
        "cors_allowed_origins": ["https://parking.example.com"],
        "seed_admin_enabled": False,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_environment_normalization_and_classification() -> None:
    assert normalize_environment(" Production ") == "production"
    assert is_production_environment("prod") is True
    assert is_production_environment("production") is True
    assert is_local_environment("development") is True
    assert is_local_environment("test") is True
    assert is_production_environment("staging") is False


def test_direct_secret_values_continue_to_work_locally() -> None:
    settings = Settings(
        _env_file=None,
        jwt_secret_key="local-direct-secret",
        database_password="local-db-password",
        database_url="",
    )

    assert settings.jwt_secret_key == "local-direct-secret"
    assert "local-db-password" in settings.database_url


def test_file_based_jwt_secret_takes_default_direct_value_place(tmp_path: Path) -> None:
    secret_path = write_secret(tmp_path, "jwt_secret.txt", "file-secret-value\n")

    settings = Settings(_env_file=None, jwt_secret_file=str(secret_path))

    assert settings.jwt_secret_key == "file-secret-value"


def test_file_based_database_password_builds_url_with_encoded_components(tmp_path: Path) -> None:
    password_path = write_secret(tmp_path, "postgres_password.txt", "p@ss word/with?\n")

    settings = Settings(
        _env_file=None,
        database_url="",
        database_user="parking user",
        database_name="parking db",
        database_password_file=str(password_path),
    )

    assert settings.database_password == "p@ss word/with?"
    assert settings.database_url == (
        "postgresql+psycopg://parking%20user:p%40ss%20word%2Fwith%3F@localhost:5432/parking%20db"
    )


def test_postgres_password_file_alias_is_supported(tmp_path: Path) -> None:
    password_path = write_secret(tmp_path, "postgres_password.txt", "postgres-file-password")

    settings = Settings(
        _env_file=None,
        database_url="",
        postgres_password_file=str(password_path),
    )

    assert settings.database_password == "postgres-file-password"


def test_secret_file_rejects_empty_file(tmp_path: Path) -> None:
    secret_path = write_secret(tmp_path, "jwt_secret.txt", "\n")

    with pytest.raises(ValidationError, match="jwt_secret_key_file must not be empty"):
        Settings(_env_file=None, jwt_secret_file=str(secret_path))


def test_secret_file_rejects_missing_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing-secret.txt"

    with pytest.raises(ValidationError, match="jwt_secret_key_file is missing or unreadable"):
        Settings(_env_file=None, jwt_secret_file=str(missing_path))


def test_conflicting_direct_and_file_secret_values_are_rejected_without_leaking_secret(
    tmp_path: Path,
) -> None:
    secret_path = write_secret(tmp_path, "jwt_secret.txt", "file-only-secret-value")
    direct_secret = "direct-only-secret-value"

    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            jwt_secret_key=direct_secret,
            jwt_secret_file=str(secret_path),
        )

    rendered_error = str(exc_info.value)
    assert "cannot be set with both" in rendered_error
    assert direct_secret not in rendered_error
    assert "file-only-secret-value" not in rendered_error


def test_database_password_file_rejects_database_url_combination(tmp_path: Path) -> None:
    password_path = write_secret(tmp_path, "postgres_password.txt", "file-db-password")

    with pytest.raises(ValidationError, match="database_url cannot be combined"):
        Settings(
            _env_file=None,
            database_url="postgresql+psycopg://user:password@db:5432/app",
            database_password_file=str(password_path),
        )


def test_database_url_builder_url_encodes_credentials() -> None:
    assert build_database_url(
        user="user name",
        password="p@ss/word",
        host="db",
        port=5432,
        name="parking db",
    ) == "postgresql+psycopg://user%20name:p%40ss%2Fword@db:5432/parking%20db"


def test_production_rejects_default_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="jwt_secret_key"):
        production_settings(jwt_secret_key="change-this-in-real-environments")


def test_production_rejects_short_jwt_secret() -> None:
    with pytest.raises(ValidationError, match=str(MIN_PRODUCTION_JWT_SECRET_LENGTH)):
        production_settings(jwt_secret_key="short-secret")


def test_production_accepts_valid_secret_and_database_password() -> None:
    settings = production_settings()

    assert settings.environment == "production"
    assert settings.jwt_secret_key == VALID_PRODUCTION_JWT_SECRET
    assert settings.database_password == VALID_PRODUCTION_DATABASE_PASSWORD


@pytest.mark.parametrize("database_password", ["", "parking_app", "postgres", "password", "example-password"])
def test_production_rejects_empty_or_example_database_password(database_password: str) -> None:
    with pytest.raises(ValidationError, match="database password"):
        production_settings(database_password=database_password)


def test_production_rejects_example_password_embedded_in_database_url() -> None:
    with pytest.raises(ValidationError, match="database password"):
        production_settings(
            database_url="postgresql+psycopg://parking_app:parking_app@db:5432/parking_app",
        )


def test_production_rejects_seed_admin_enabled() -> None:
    with pytest.raises(ValidationError, match="seed admin"):
        production_settings(seed_admin_enabled=True)


def test_production_rejects_debug_logging() -> None:
    with pytest.raises(ValidationError, match="debug logging"):
        production_settings(log_level="DEBUG")


def test_production_rejects_local_or_http_cors_origins() -> None:
    with pytest.raises(ValidationError, match="local development hosts"):
        production_settings(cors_allowed_origins=["https://localhost"])
    with pytest.raises(ValidationError, match="must use HTTPS"):
        production_settings(cors_allowed_origins=["http://parking.example.com"])


def test_wildcard_cors_with_credentials_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            cors_allowed_origins=["*"],
            cors_allow_credentials=True,
        )


def test_test_environment_allows_local_defaults_and_scheduler_settings() -> None:
    settings = Settings(
        _env_file=None,
        environment="test",
        assignment_scheduler_enabled=True,
        assignment_scheduler_interval_seconds=5,
    )

    assert settings.environment == "test"
    assert settings.jwt_secret_key == "change-this-in-real-environments"
    assert settings.assignment_scheduler_enabled is True
