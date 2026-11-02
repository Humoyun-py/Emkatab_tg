"""Tests for Telegram user authorization middleware."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.types import User

from bot import AuthorizationMiddleware


@pytest.mark.asyncio
async def test_authorized_user_reaches_handler():
    """Updates from an allow-listed Telegram user proceed to the handler."""
    downstream = AsyncMock(return_value="handled")
    middleware = AuthorizationMiddleware(frozenset({7782143104}))
    event = SimpleNamespace(
        from_user=User(id=7782143104, is_bot=False, first_name="Test")
    )

    result = await middleware(downstream, event, {})

    assert result == "handled"
    downstream.assert_awaited_once_with(event, {})


@pytest.mark.asyncio
async def test_unauthorized_user_is_blocked():
    """Updates from any user outside the allow-list never reach the handler."""
    downstream = AsyncMock(return_value="handled")
    middleware = AuthorizationMiddleware(frozenset({7782143104}))
    event = SimpleNamespace(
        from_user=User(id=12345, is_bot=False, first_name="Test")
    )

    result = await middleware(downstream, event, {})

    assert result is None
    downstream.assert_not_awaited()
