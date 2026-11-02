"""Tests for environment-based settings validation."""

import pytest

import config
from config import Settings


@pytest.fixture(autouse=True)
def _isolate_environment(monkeypatch):
    """Ignore the developer's real .env file and start from a clean environment."""
    monkeypatch.setattr(config, "load_dotenv", lambda *args, **kwargs: False)
    for name in (
        "BOT_TOKEN",
        "AUTHORIZED_USER_IDS",
        "DATABASE_URL",
        "LOGIN_URL",
        "LOGIN_CHECK_ENABLED",
    ):
        monkeypatch.delenv(name, raising=False)


def _minimal_env(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("AUTHORIZED_USER_IDS", "111")


def test_login_check_is_disabled_by_default(monkeypatch):
    """Credential checking stays off unless explicitly enabled."""
    _minimal_env(monkeypatch)

    assert Settings.from_environment().login_check_enabled is False


@pytest.mark.parametrize("raw_value", ["true", "TRUE", " yes ", "1", "on"])
def test_login_check_accepts_truthy_values(monkeypatch, raw_value):
    """Common truthy spellings enable the login check."""
    _minimal_env(monkeypatch)
    monkeypatch.setenv("LOGIN_CHECK_ENABLED", raw_value)

    assert Settings.from_environment().login_check_enabled is True


@pytest.mark.parametrize("raw_value", ["false", "0", "no", "", "maybe"])
def test_login_check_treats_other_values_as_disabled(monkeypatch, raw_value):
    """Anything that is not an explicit truthy value keeps the check off."""
    _minimal_env(monkeypatch)
    monkeypatch.setenv("LOGIN_CHECK_ENABLED", raw_value)

    assert Settings.from_environment().login_check_enabled is False


def test_login_url_defaults_to_emaktab_login(monkeypatch):
    """Without an override, the login URL points at the official host."""
    _minimal_env(monkeypatch)

    assert Settings.from_environment().login_url == "https://login.emaktab.uz/"


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
