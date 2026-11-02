"""Authentication-check service interface and unavailable implementation."""

from dataclasses import dataclass
from typing import Protocol

from database.models import AccountType, CheckStatus


@dataclass(frozen=True, slots=True)
class AuthenticationResult:
    """Outcome of an authentication attempt without any credential data."""

    account_type: AccountType
    status: CheckStatus
    message: str


class LoginChecker(Protocol):
    """Interface for a permitted authentication-check implementation."""

    async def availability(
        self, account_type: AccountType
    ) -> AuthenticationResult:
        """Describe whether a permitted checker is currently available."""
        ...

    async def check(
        self,
        account_type: AccountType,
        login: str,
        password: str,
    ) -> AuthenticationResult:
        """Check authentication using credentials held only for this call."""
        ...


class UnavailableLoginChecker:
    """Checker used until a permitted eMaktab authentication method exists."""

    async def availability(
        self, account_type: AccountType
    ) -> AuthenticationResult:
        """Report that no permitted authentication method is configured."""
        return AuthenticationResult(
            account_type=account_type,
            status=CheckStatus.UNKNOWN,
            message=(
                "Authentication verification is unavailable because no permitted "
                "authentication method has been confirmed."
            ),
        )

    async def check(
        self,
        account_type: AccountType,
        login: str,
        password: str,
    ) -> AuthenticationResult:
        """Return UNKNOWN without inspecting, logging, or retaining credentials."""
        del login, password
        return await self.availability(account_type)
