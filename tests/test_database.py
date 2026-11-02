"""Tests for asynchronous database initialization and report persistence."""

from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import inspect, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from database.engine import (
    create_database_engine,
    create_session_factory,
    initialize_database,
)
from database.models import AccountType, Base, CheckBatch, CheckResult, CheckStatus
from database.queries import (
    CheckResultInput,
    get_or_create_user,
    get_user_history,
    record_check_batch,
)


@pytest_asyncio.fixture
async def session_factory():
    """Create a fresh in-memory SQLite schema for each test."""
    engine = create_database_engine("sqlite+aiosqlite:///:memory:")
    await initialize_database(engine)
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_database_initialization_creates_required_tables(session_factory):
    """Initialization creates the three required tables."""
    async with session_factory.kw["bind"].connect() as connection:
        table_names = await connection.run_sync(
            lambda sync_connection: set(
                inspect(sync_connection).get_table_names()
            )
        )

    assert {"users", "check_batches", "check_results"} <= table_names


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "expected_counts"),
    [
        (CheckStatus.SUCCESS, (1, 1, 0, 0)),
        (CheckStatus.INVALID_CREDENTIALS, (1, 0, 1, 0)),
        (CheckStatus.UNKNOWN, (1, 0, 0, 1)),
    ],
)
async def test_record_check_result_statuses(
    session_factory, status, expected_counts
):
    """Success, invalid credentials, and unknown outcomes are counted distinctly."""
    async with session_factory.begin() as session:
        user = await get_or_create_user(session, telegram_id=1001)
        batch = await record_check_batch(
            session,
            user_id=user.id,
            results=[
                CheckResultInput(
                    account_type=AccountType.STUDENT,
                    account_label="student-test",
                    status=status,
                )
            ],
        )

    assert (
        batch.total_count,
        batch.success_count,
        batch.invalid_count,
        batch.unknown_count,
    ) == expected_counts


@pytest.mark.asyncio
async def test_history_is_scoped_to_telegram_user(session_factory):
    """History returns only reports belonging to the requested user."""
    async with session_factory.begin() as session:
        owner = await get_or_create_user(session, telegram_id=1001)
        other_user = await get_or_create_user(session, telegram_id=2002)
        await record_check_batch(
            session,
            user_id=owner.id,
            results=[
                CheckResultInput(
                    AccountType.STUDENT, "owned-report", CheckStatus.SUCCESS
                )
            ],
        )
        await record_check_batch(
            session,
            user_id=other_user.id,
            results=[
                CheckResultInput(
                    AccountType.PARENT, "other-report", CheckStatus.UNKNOWN
                ),
                CheckResultInput(
                    AccountType.STUDENT, "other-report-2", CheckStatus.UNKNOWN
                ),
            ],
        )

    async with session_factory() as session:
        batches = await get_user_history(session, telegram_id=1001)

    assert len(batches) == 1
    assert batches[0].total_count == 1


@pytest.mark.asyncio
async def test_credentials_are_not_part_of_database_schema_or_result_input(
    session_factory,
):
    """Persisted result schema and result data have no credential fields."""
    test_login = "not-a-real-login"
    test_password = "not-a-real-password"

    async with session_factory.begin() as session:
        user = await get_or_create_user(session, telegram_id=1001)
        batch = await record_check_batch(
            session,
            user_id=user.id,
            results=[
                CheckResultInput(
                    AccountType.STUDENT, "student-test", CheckStatus.UNKNOWN
                )
            ],
        )

    async with session_factory() as session:
        stored_batch = (
            await session.execute(
                select(CheckBatch.__table__).where(CheckBatch.id == batch.id)
            )
        ).mappings().one()
        stored_result = (
            await session.execute(
                select(CheckResult.__table__).where(
                    CheckResult.batch_id == batch.id
                )
            )
        ).mappings().one()

    column_names = {
        column.name
        for table in Base.metadata.tables.values()
        for column in table.columns
    }
    stored_values = repr((dict(stored_batch), dict(stored_result)))
    assert not column_names.intersection(
        {"password", "login", "credentials", "cookie", "session_token"}
    )
    assert test_login not in stored_values
    assert test_password not in stored_values


@pytest.mark.asyncio
async def test_database_errors_are_not_silently_converted_to_results():
    """Database query failures remain visible to callers."""
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = SQLAlchemyError("database unavailable")

    with pytest.raises(SQLAlchemyError, match="database unavailable"):
        await get_or_create_user(session, telegram_id=1001)
