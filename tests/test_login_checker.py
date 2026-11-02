"""Tests for the authentication checker interface."""

import pytest

from database.models import AccountType, CheckStatus
from services.login_checker import LoginChecker, UnavailableLoginChecker


@pytest.mark.asyncio
@pytest.mark.parametrize("account_type", list(AccountType))
async def test_unavailable_checker_reports_unknown(account_type):
    """The unavailable implementation never claims authentication succeeded."""
    checker: LoginChecker = UnavailableLoginChecker()

    result = await checker.availability(account_type)

    assert result.account_type is account_type
    assert result.status is CheckStatus.UNKNOWN
    assert "unavailable" in result.message.lower()


@pytest.mark.asyncio
async def test_unavailable_check_does_not_return_or_retain_credentials():
    """Credentials passed to the interface are absent from its result."""
    login = "test-login-only"
    password = "test-password-only"
    checker = UnavailableLoginChecker()

    result = await checker.check(AccountType.STUDENT, login, password)
    representation = repr(result)

    assert result.status is CheckStatus.UNKNOWN
    assert login not in representation
    assert password not in representation
    assert not hasattr(checker, "login")
    assert not hasattr(checker, "password")
