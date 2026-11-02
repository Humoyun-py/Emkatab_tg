"""Async SQLite engine and schema initialization."""

from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from database.models import Base


def _enable_sqlite_foreign_keys(dbapi_connection: Any, *args: Any) -> None:
    """Enable foreign-key enforcement for each SQLite connection."""
    del args
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def create_database_engine(database_url: str) -> AsyncEngine:
    """Create an async SQLAlchemy engine and enable SQLite constraints."""
    engine = create_async_engine(database_url)
    if database_url.startswith("sqlite+aiosqlite://"):
        event.listen(engine.sync_engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory for the supplied engine."""
    return async_sessionmaker(engine, expire_on_commit=False)


async def initialize_database(engine: AsyncEngine) -> None:
    """Create the initial database tables if they do not exist."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
