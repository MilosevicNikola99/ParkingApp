from functools import lru_cache
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_JWT_SECRET_KEY = "change-this-in-real-environments"
DEFAULT_DATABASE_PASSWORD = "parking_app"
MIN_PRODUCTION_JWT_SECRET_LENGTH = 32

LOCAL_ENVIRONMENTS = frozenset({"local", "development", "dev", "test", "testing"})
PRODUCTION_ENVIRONMENTS = frozenset({"production", "prod"})

JWT_SECRET_PLACEHOLDERS = frozenset(
    {
        DEFAULT_JWT_SECRET_KEY,
        "secret",
        "jwt-secret",
        "your-secret-key",
        "your-jwt-secret",
        "example-secret",
        "test-secret-key",
        "auth-service-test-secret",
    },
)
DATABASE_PASSWORD_PLACEHOLDERS = frozenset(
    {
        "",
        DEFAULT_DATABASE_PASSWORD,
        "postgres",
        "password",
        "changeme",
        "change-me",
        "example",
        "example-password",
        "your-database-password",
    },
)


def normalize_environment(value: str) -> str:
    return value.strip().lower()


def is_production_environment(value: str) -> bool:
    return normalize_environment(value) in PRODUCTION_ENVIRONMENTS


def is_local_environment(value: str) -> bool:
    return normalize_environment(value) in LOCAL_ENVIRONMENTS


def trim_single_trailing_newline(value: str) -> str:
    if value.endswith("\r\n"):
        return value[:-2]
    if value.endswith("\n") or value.endswith("\r"):
        return value[:-1]
    return value


def read_secret_file(path: str, setting_name: str) -> str:
    try:
        raw_value = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"{setting_name}_file is missing or unreadable") from exc

    value = trim_single_trailing_newline(raw_value)
    if value == "":
        raise ValueError(f"{setting_name}_file must not be empty")
    return value


def is_placeholder_secret(value: str, placeholders: frozenset[str]) -> bool:
    return value.strip().lower() in {placeholder.lower() for placeholder in placeholders}


def resolve_secret_value(
    *,
    setting_name: str,
    direct_value: str,
    file_path: str | None,
    default_values: frozenset[str],
) -> str:
    if not file_path:
        return direct_value

    file_value = read_secret_file(file_path, setting_name)
    if direct_value not in default_values and direct_value != file_value:
        raise ValueError(
            f"{setting_name} cannot be set with both a custom direct value and {setting_name}_file",
        )
    return file_value


def build_database_url(
    *,
    user: str,
    password: str,
    host: str,
    port: int,
    name: str,
) -> str:
    encoded_user = quote(user, safe="")
    encoded_password = quote(password, safe="")
    encoded_name = quote(name, safe="")
    return f"postgresql+psycopg://{encoded_user}:{encoded_password}@{host}:{port}/{encoded_name}"


class Settings(BaseSettings):
    app_name: str = "Parking Management API"
    environment: str = "local"
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "parking_app"
    database_user: str = "parking_app"
    database_password: str = DEFAULT_DATABASE_PASSWORD
    database_password_file: str | None = None
    postgres_password_file: str | None = None
    database_url: str = ""
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=5, ge=0, le=50)
    db_pool_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    db_pool_recycle_seconds: int = Field(default=1800, ge=60, le=86_400)
    db_pool_pre_ping: bool = True
    jwt_secret_key: str = Field(default=DEFAULT_JWT_SECRET_KEY)
    jwt_secret_file: str | None = None
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    same_team_priority_window_hours: int = Field(default=2, ge=0)
    recent_win_fairness_window_days: int = Field(default=30, ge=1)
    recent_win_soft_limit: int = Field(default=2, ge=1)
    assignment_scheduler_enabled: bool = False
    assignment_scheduler_interval_seconds: int = Field(default=60, ge=5, le=86_400)
    assignment_scheduler_batch_limit: int = Field(default=100, ge=1, le=1_000)
    assignment_scheduler_lock_key: int = Field(default=740_730_001, ge=1, le=9_223_372_036_854_775_807)
    assignment_scheduler_run_immediately: bool = True
    metrics_enabled: bool = True
    metrics_path: str = "/metrics"
    scheduler_metrics_port: int = Field(default=9101, ge=1, le=65535)
    readiness_database_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    log_level: str = "INFO"
    log_json: bool = True
    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:8080"],
    )
    cors_allow_credentials: bool = False
    seed_admin_enabled: bool = False
    seed_admin_email: str | None = None
    seed_admin_username: str | None = None
    seed_admin_password: SecretStr | None = None
    seed_admin_first_name: str | None = None
    seed_admin_last_name: str | None = None
    seed_admin_update_password: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        hide_input_in_errors=True,
    )

    @field_validator("environment")
    @classmethod
    def normalize_environment(cls, value: str) -> str:
        normalized = normalize_environment(value)
        if not normalized:
            raise ValueError("environment must not be empty")
        return normalized

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.upper()
        allowed_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if normalized not in allowed_levels:
            raise ValueError(f"log_level must be one of {sorted(allowed_levels)}")
        return normalized

    @field_validator("metrics_path")
    @classmethod
    def validate_metrics_path(cls, value: str) -> str:
        normalized = value.strip()
        if (
            not normalized.startswith("/")
            or len(normalized) == 1
            or any(character.isspace() for character in normalized)
            or "{" in normalized
            or "}" in normalized
            or "?" in normalized
            or "#" in normalized
        ):
            raise ValueError("metrics_path must be a fixed absolute path without parameters")
        return normalized.rstrip("/")

    @field_validator("cors_allowed_origins")
    @classmethod
    def validate_cors_allowed_origins(cls, origins: list[str]) -> list[str]:
        if not origins:
            raise ValueError("cors_allowed_origins must contain at least one exact origin")

        normalized_origins: list[str] = []
        for origin in origins:
            candidate = origin.strip()
            if candidate == "*":
                raise ValueError("wildcard CORS origins are not supported")
            if any(character.isspace() for character in candidate) or "\\" in candidate:
                raise ValueError(f"invalid CORS origin: {candidate}")

            parsed = urlsplit(candidate)
            try:
                parsed.port
            except ValueError as exc:
                raise ValueError(f"invalid CORS origin: {candidate}") from exc

            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(f"CORS origin must be an exact HTTP(S) origin: {candidate}")

            normalized_origin = candidate.rstrip("/")
            if normalized_origin not in normalized_origins:
                normalized_origins.append(normalized_origin)

        return normalized_origins

    @model_validator(mode="after")
    def resolve_secret_files_and_validate_production(self) -> "Settings":
        database_password_file = self._resolve_database_password_file()
        self.jwt_secret_key = resolve_secret_value(
            setting_name="jwt_secret_key",
            direct_value=self.jwt_secret_key,
            file_path=self.jwt_secret_file,
            default_values=JWT_SECRET_PLACEHOLDERS,
        )
        if self.database_url and database_password_file:
            raise ValueError("database_url cannot be combined with a database password file")
        self.database_password = resolve_secret_value(
            setting_name="database_password",
            direct_value=self.database_password,
            file_path=database_password_file,
            default_values=frozenset({DEFAULT_DATABASE_PASSWORD}),
        )
        if not self.database_url:
            self.database_url = build_database_url(
                user=self.database_user,
                password=self.database_password,
                host=self.database_host,
                port=self.database_port,
                name=self.database_name,
            )

        if not is_production_environment(self.environment):
            return self

        local_hosts = {"localhost", "127.0.0.1", "::1"}
        if any(urlsplit(origin).hostname in local_hosts for origin in self.cors_allowed_origins):
            raise ValueError("production CORS origins must not use local development hosts")
        if any(urlsplit(origin).scheme != "https" for origin in self.cors_allowed_origins):
            raise ValueError("production CORS origins must use HTTPS")
        if is_placeholder_secret(self.jwt_secret_key, JWT_SECRET_PLACEHOLDERS):
            raise ValueError("production jwt_secret_key must be explicitly configured")
        if len(self.jwt_secret_key) < MIN_PRODUCTION_JWT_SECRET_LENGTH:
            raise ValueError(
                f"production jwt_secret_key must be at least {MIN_PRODUCTION_JWT_SECRET_LENGTH} characters",
            )
        if is_placeholder_secret(
            self._effective_database_password_for_validation(),
            DATABASE_PASSWORD_PLACEHOLDERS,
        ):
            raise ValueError("production database password must be explicitly configured")
        if self.seed_admin_enabled:
            raise ValueError("seed admin must be disabled in production")
        if self.log_level == "DEBUG":
            raise ValueError("debug logging is not allowed in production")

        return self

    def _resolve_database_password_file(self) -> str | None:
        configured_files = [
            file_path
            for file_path in (self.database_password_file, self.postgres_password_file)
            if file_path
        ]
        if not configured_files:
            return None
        if len(set(configured_files)) > 1:
            raise ValueError("database password file configured through multiple different variables")
        return configured_files[0]

    def _effective_database_password_for_validation(self) -> str:
        parsed = urlsplit(self.database_url)
        if parsed.password is not None:
            return unquote(parsed.password)
        return self.database_password


@lru_cache
def get_settings() -> Settings:
    return Settings()
