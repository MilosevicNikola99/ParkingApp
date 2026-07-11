from pydantic import ValidationError
import pytest

from app.core.config import Settings
from app.db.session import engine_kwargs_from_settings


def test_database_pool_settings_have_conservative_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.db_pool_size == 5
    assert settings.db_max_overflow == 5
    assert settings.db_pool_timeout_seconds == 30
    assert settings.db_pool_recycle_seconds == 1800
    assert settings.db_pool_pre_ping is True


def test_database_pool_settings_accept_valid_values() -> None:
    settings = Settings(
        _env_file=None,
        db_pool_size=10,
        db_max_overflow=3,
        db_pool_timeout_seconds=5.5,
        db_pool_recycle_seconds=600,
        db_pool_pre_ping=False,
    )

    assert settings.db_pool_size == 10
    assert settings.db_max_overflow == 3
    assert settings.db_pool_timeout_seconds == 5.5
    assert settings.db_pool_recycle_seconds == 600
    assert settings.db_pool_pre_ping is False


@pytest.mark.parametrize(
    "field_name,value",
    [
        ("db_pool_size", 0),
        ("db_pool_size", -1),
        ("db_max_overflow", -1),
        ("db_pool_timeout_seconds", 0),
        ("db_pool_timeout_seconds", -1),
        ("db_pool_recycle_seconds", 0),
        ("db_pool_recycle_seconds", -1),
    ],
)
def test_database_pool_settings_reject_zero_or_negative_values(
    field_name: str,
    value: int,
) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field_name: value})


def test_database_pool_settings_reject_excessive_values() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, db_pool_size=51)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, db_max_overflow=51)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, db_pool_timeout_seconds=121)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, db_pool_recycle_seconds=86_401)


@pytest.mark.parametrize(
    "raw_value,expected",
    [
        ("true", True),
        ("false", False),
        ("1", True),
        ("0", False),
    ],
)
def test_database_pool_pre_ping_boolean_parsing(raw_value: str, expected: bool) -> None:
    settings = Settings(_env_file=None, db_pool_pre_ping=raw_value)

    assert settings.db_pool_pre_ping is expected


def test_engine_kwargs_include_configured_pool_values_for_postgresql() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://user:password@db:5432/app",
        db_pool_size=7,
        db_max_overflow=2,
        db_pool_timeout_seconds=9,
        db_pool_recycle_seconds=120,
        db_pool_pre_ping=False,
    )

    assert engine_kwargs_from_settings(settings) == {
        "pool_pre_ping": False,
        "pool_size": 7,
        "max_overflow": 2,
        "pool_timeout": 9,
        "pool_recycle": 120,
    }


def test_engine_kwargs_skip_queue_pool_values_for_sqlite_compatibility() -> None:
    settings = Settings(
        _env_file=None,
        database_url="sqlite+pysqlite:///:memory:",
        db_pool_size=7,
        db_max_overflow=2,
        db_pool_timeout_seconds=9,
        db_pool_recycle_seconds=120,
        db_pool_pre_ping=True,
    )

    assert engine_kwargs_from_settings(settings) == {"pool_pre_ping": True}
