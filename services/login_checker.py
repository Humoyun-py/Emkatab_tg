"""Authentication-check service interface and implementations."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Protocol

import requests

from database.models import AccountType, CheckStatus


logger = logging.getLogger(__name__)

LOGIN_REQUEST_TIMEOUT = 15.0
_HTTP_OK = 200
_HTTP_REJECTED = frozenset({401, 403})


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


class EMaktabLoginChecker:
    """Checks eMaktab credentials with one HTTP POST per call.

    Credentials are sent only in the request body and are not logged,
    stored, or included in the returned result.
    """

    def __init__(self, login_url: str, timeout: float = LOGIN_REQUEST_TIMEOUT) -> None:
        self.login_url = login_url
        self.timeout = timeout

    async def availability(
        self,
        account_type: AccountType,
    ) -> AuthenticationResult:
        return AuthenticationResult(
            account_type=account_type,
            status=CheckStatus.UNKNOWN,
            message="Login verification is available.",
        )

    async def check(
        self,
        account_type: AccountType,
        login: str,
        password: str,
    ) -> AuthenticationResult:
        """Return SUCCESS, INVALID_CREDENTIALS, or UNKNOWN for one login attempt."""
        try:
            response = await asyncio.to_thread(
                requests.post,
                self.login_url,
                data={"login": login, "password": password},
                timeout=self.timeout,
            )
        except requests.RequestException as error:
            # Log only the exception type: the message may echo request details.
            logger.error(
                "Login request failed.",
                extra={"error_type": type(error).__name__},
            )
            return self._result(account_type, CheckStatus.UNKNOWN)

        # A 200 can be the login form itself (the page re-rendered without a
        # session), so it is not evidence that the credentials were accepted.
        if response.status_code in _HTTP_REJECTED:
            return self._result(account_type, CheckStatus.INVALID_CREDENTIALS)
        if response.status_code != _HTTP_OK:
            logger.warning(
                "Login returned an unexpected status.",
                extra={"status_code": response.status_code},
            )
        return self._result(account_type, CheckStatus.UNKNOWN)

    @staticmethod
    def _result(account_type: AccountType, status: CheckStatus) -> AuthenticationResult:
        messages = {
            CheckStatus.SUCCESS: "Login muvaffaqiyatli.",
            CheckStatus.INVALID_CREDENTIALS: "Login yoki parol noto‘g‘ri.",
            CheckStatus.UNKNOWN: "Natijani aniqlab bo‘lmadi. Keyinroq urinib ko‘ring.",
        }
        return AuthenticationResult(
            account_type=account_type,
            status=status,
            message=messages[status],
        )
