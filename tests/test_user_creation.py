"""Tests for idempotent user creation under concurrent inserts."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from database.models import User
from database.queries import get_or_create_user


@pytest.mark.asyncio
async def test_integrity_error_returns_row_inserted_by_another_update():
    """If another update inserted the user first, the existing row is returned."""
    existing = User(id=5, telegram_id=1001)

    session = MagicMock()
    missing = MagicMock()
    missing.scalar_one_or_none.return_value = None
    found = MagicMock()
    found.scalar_one.return_value = existing
    session.execute = AsyncMock(side_effect=[missing, found])
    session.flush = AsyncMock(side_effect=IntegrityError("insert", {}, Exception()))

    savepoint = MagicMock()
    savepoint.__aenter__ = AsyncMock(return_value=None)
    savepoint.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested = MagicMock(return_value=savepoint)

    user = await get_or_create_user(session, telegram_id=1001)

    assert user is existing
    assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_existing_user_is_returned_without_insert():
    """A known user is returned directly and no savepoint is opened."""
    existing = User(id=7, telegram_id=2002)

    session = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing
    session.execute = AsyncMock(return_value=result)
    session.begin_nested = MagicMock()

    user = await get_or_create_user(session, telegram_id=2002)

    assert user is existing
    session.begin_nested.assert_not_called()
