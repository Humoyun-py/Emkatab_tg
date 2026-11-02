"""Authentication-check service interface and safe unavailable implementation."""

from dataclasses import dataclass
from typing import Protocol

from database.models import AccountType, CheckStatus


@dataclass(frozen=True, slots=True)
class AuthenticationResult:
    """Authentication result without storing credential information."""

    account_type: AccountType
    status: CheckStatus
    message: str


class LoginChecker(Protocol):
    """Interface for an approved authentication implementation."""

    async def availability(
        self,
        account_type: AccountType,
    ) -> AuthenticationResult:
        """Check whether authentication verification is available."""
        ...

    async def check(
        self,
        account_type: AccountType,
        login: str,
        password: str,
    ) -> AuthenticationResult:
        """Check authentication without retaining credentials."""
        ...


class UnavailableLoginChecker:
    """Safe fallback until an approved authentication method is available."""

    async def availability(
        self,
        account_type: AccountType,
    ) -> AuthenticationResult:
        return AuthenticationResult(
            account_type=account_type,
            status=CheckStatus.UNKNOWN,
            message=(
                "Login verification is currently unavailable. "
                "An approved authentication method has not been configured."
            ),
        )

    async def check(
        self,
        account_type: AccountType,
        login: str,
        password: str,
    ) -> AuthenticationResult:
        # Never log, store, or transmit credentials.
        del login, password

        return await self.availability(account_type)