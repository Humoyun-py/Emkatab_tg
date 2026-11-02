"""Tests for environment-based settings validation."""

import pytest

import config
from config import Settings


@pytest.fixture(autouse=True)
def _isolate_environment(monkeypatch):
    """Ignore the developer's real .env file and start from a clean environment."""
    monkeypatch.setattr(config, "load_dotenv", lambda *args, **kwargs: False)
    for name in ("BOT_TOKEN", "AUTHORIZED_USER_IDS", "DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)


def test_valid_settings_are_parsed(monkeypatch):
    """Comma-separated IDs are parsed into a frozen set of integers."""
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("AUTHORIZED_USER_IDS", " 111, 222 ,111")

    settings = Settings.from_environment()

    assert settings.bot_token == "token"
    assert settings.authorized_user_ids == frozenset({111, 222})
    assert settings.database_url == "sqlite+aiosqlite:///./emaktab.db"


def test_missing_bot_token_is_rejected(monkeypatch):
    """A missing or blank bot token stops startup."""
    monkeypatch.setenv("BOT_TOKEN", "   ")
    monkeypatch.setenv("AUTHORIZED_USER_IDS", "111")

    with pytest.raises(ValueError, match="BOT_TOKEN"):
        Settings.from_environment()


def test_empty_authorized_ids_are_rejected(monkeypatch):
    """At least one authorized Telegram user is required."""
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("AUTHORIZED_USER_IDS", "")

    with pytest.raises(ValueError, match="AUTHORIZED_USER_IDS"):
        Settings.from_environment()


@pytest.mark.parametrize("raw_ids", ["abc", "1,two", "0", "-5", "1,,2"])
def test_invalid_authorized_ids_are_rejected(monkeypatch, raw_ids):
    """Non-integer, zero, negative, or empty entries are rejected."""
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("AUTHORIZED_USER_IDS", raw_ids)

    with pytest.raises(ValueError, match="positive integers"):
        Settings.from_environment()


def test_non_async_sqlite_url_is_rejected(monkeypatch):
    """Only the async SQLite driver is accepted."""
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("AUTHORIZED_USER_IDS", "111")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://localhost/db")

    with pytest.raises(ValueError, match="async SQLite"):
        Settings.from_environment()
