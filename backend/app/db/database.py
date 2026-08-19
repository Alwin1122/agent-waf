"""Database engine, schema initialization and session management."""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.models import Base


class Database:
    """Own the SQLAlchemy engine and short-lived session factory."""

    def __init__(
        self,
        url: str,
        *,
        echo: bool = False,
        pool_size: int = 5,
        connect_timeout_seconds: int = 5,
    ) -> None:
        connect_args = (
            {"connect_timeout": connect_timeout_seconds}
            if url.startswith(("postgresql://", "postgresql+"))
            else {}
        )
        self.engine: Engine = create_engine(
            url,
            echo=echo,
            pool_pre_ping=True,
            pool_size=pool_size,
            connect_args=connect_args,
        )
        self.session_factory = sessionmaker(
            bind=self.engine,
            class_=Session,
            expire_on_commit=False,
        )

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    def check_connection(self) -> None:
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def dispose(self) -> None:
        self.engine.dispose()


@lru_cache
def get_database() -> Database:
    """Return the configured process-wide database manager."""
    settings = get_settings()
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL is required for database access")
    return Database(
        settings.database_url.get_secret_value(),
        echo=settings.database_echo,
        pool_size=settings.database_pool_size,
        connect_timeout_seconds=settings.database_connect_timeout_seconds,
    )


def get_db_session() -> Iterator[Session]:
    """FastAPI-compatible transactional session dependency."""
    database = get_database()
    with database.session_factory() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
