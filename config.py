"""Environment-based configuration for the eMaktab Checker Bot."""

from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Settings:
    """Validated settings required to start the Telegram bot."""

    bot_token: str
    authorized_user_ids: frozenset[int]
    database_url: str
    login_url: str

    @classmethod
    def from_environment(cls) -> "Settings":
        """Load settings from the environment and the local .env file."""
        load_dotenv()

        bot_token = os.getenv("BOT_TOKEN", "").strip()
        if not bot_token:
            raise ValueError(
                "BOT_TOKEN must be set in the environment or .env file."
            )

        raw_authorized_ids = os.getenv("AUTHORIZED_USER_IDS", "")
        if not raw_authorized_ids.strip():
            raise ValueError(
                "AUTHORIZED_USER_IDS must contain at least one Telegram user ID."
            )

        authorized_user_ids: set[int] = set()

        for raw_user_id in raw_authorized_ids.split(","):
            value = raw_user_id.strip()

            try:
                user_id = int(value)
            except ValueError as error:
                raise ValueError(
                    "AUTHORIZED_USER_IDS must be a comma-separated "
                    "list of positive integers."
                ) from error

            if user_id <= 0:
                raise ValueError(
                    "AUTHORIZED_USER_IDS must contain positive integers."
                )

            authorized_user_ids.add(user_id)

        database_url = os.getenv(
            "DATABASE_URL",
            "sqlite+aiosqlite:///./emaktab.db"
        ).strip()

        if not database_url.startswith("sqlite+aiosqlite:///"):
            raise ValueError(
                "DATABASE_URL must use the async SQLite driver."
            )

        login_url = os.getenv(
            "LOGIN_URL",
            "https://login.emaktab.uz/"
        ).strip()

        return cls(
            bot_token=bot_token,
            authorized_user_ids=frozenset(authorized_user_ids),
            database_url=database_url,
            login_url=login_url,
        )