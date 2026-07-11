from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings


settings = get_settings()


def engine_kwargs_from_settings(settings: Settings) -> dict[str, object]:
    kwargs: dict[str, object] = {"pool_pre_ping": settings.db_pool_pre_ping}

    if settings.database_url.startswith("sqlite"):
        return kwargs

    kwargs.update(
        {
            "pool_size": settings.db_pool_size,
            "max_overflow": settings.db_max_overflow,
            "pool_timeout": settings.db_pool_timeout_seconds,
            "pool_recycle": settings.db_pool_recycle_seconds,
        },
    )
    return kwargs


engine = create_engine(settings.database_url, **engine_kwargs_from_settings(settings))
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
