"""Tests for the eMaktab login check: HTTP mapping and the Telegram flow.

No test contacts eMaktab. HTTP is replaced by a stub, and Telegram is replaced
by an in-process fake session that records outgoing Bot API calls.
"""

from types import SimpleNamespace

import pytest
import pytest_asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy import select

import services.login_checker as login_checker_module
from database.engine import create_database_engine, create_session_factory, initialize_database
from database.models import AccountType, CheckBatch, CheckResult, CheckStatus
from handlers.account_type import router as account_type_router
from handlers.login_check import router as login_check_router
from tests.telegram_fakes import FakeSession, callback_update as _callback_update, message_update as _message_update
from services.login_checker import (
    AuthenticationResult,
    EMaktabLoginChecker,
    UnavailableLoginChecker,
)
from states.login import LoginCheck


LOGIN = "tst-login-value"
PASSWORD = "tst-password-value"
USER_ID = 111


# --- EMaktabLoginChecker: HTTP status mapping -------------------------------


def _fake_post(status_code=None, error=None, record=None):
    def post(url, **kwargs):
        if record is not None:
            record.update(url=url, **kwargs)
        if error is not None:
            raise error
        return SimpleNamespace(status_code=status_code, text="<html>secret echo</html>")

    return post


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (200, CheckStatus.UNKNOWN),
        (401, CheckStatus.INVALID_CREDENTIALS),
        (403, CheckStatus.INVALID_CREDENTIALS),
        (500, CheckStatus.UNKNOWN),
        (302, CheckStatus.UNKNOWN),
    ],
)
async def test_status_codes_map_to_check_status(monkeypatch, status_code, expected):
    """Each HTTP status maps to exactly one check outcome."""
    monkeypatch.setattr(login_checker_module.requests, "post", _fake_post(status_code=status_code))
    checker = EMaktabLoginChecker("https://example.invalid/login")

    result = await checker.check(AccountType.STUDENT, LOGIN, PASSWORD)

    assert result.status is expected


@pytest.mark.asyncio
async def test_credentials_go_in_body_only_and_timeout_is_set(monkeypatch):
    """Credentials are POSTed as form data, never placed in the URL."""
    record = {}
    monkeypatch.setattr(login_checker_module.requests, "post", _fake_post(status_code=200, record=record))
    checker = EMaktabLoginChecker("https://example.invalid/login", timeout=7)

    await checker.check(AccountType.PARENT, LOGIN, PASSWORD)

    assert record["url"] == "https://example.invalid/login"
    assert record["data"] == {"login": LOGIN, "password": PASSWORD}
    assert record["timeout"] == 7


@pytest.mark.asyncio
async def test_network_error_is_unknown_and_logs_only_error_type(monkeypatch, caplog):
    """A transport failure yields UNKNOWN and no credential text in logs."""
    import requests

    monkeypatch.setattr(
        login_checker_module.requests,
        "post",
        _fake_post(error=requests.ConnectionError(f"failed for {LOGIN} {PASSWORD}")),
    )
    checker = EMaktabLoginChecker("https://example.invalid/login")

    with caplog.at_level("DEBUG"):
        result = await checker.check(AccountType.STUDENT, LOGIN, PASSWORD)

    assert result.status is CheckStatus.UNKNOWN
    assert LOGIN not in caplog.text
    assert PASSWORD not in caplog.text
    failure = next(r for r in caplog.records if r.getMessage() == "Login request failed.")
    assert failure.error_type == "ConnectionError"


@pytest.mark.asyncio
async def test_result_representation_excludes_credentials(monkeypatch):
    """The returned result never echoes the login or password."""
    monkeypatch.setattr(login_checker_module.requests, "post", _fake_post(status_code=401))
    checker = EMaktabLoginChecker("https://example.invalid/login")

    result = await checker.check(AccountType.STUDENT, LOGIN, PASSWORD)
    representation = repr(result)

    assert LOGIN not in representation
    assert PASSWORD not in representation
    assert "secret echo" not in representation


# --- Telegram flow -----------------------------------------------------------


class StubChecker:
    """Returns a fixed outcome and remembers what it was asked to check."""

    def __init__(self, status=CheckStatus.SUCCESS):
        self.status = status
        self.seen = []

    async def availability(self, account_type):
        raise AssertionError("availability must not be used in the login flow")

    async def check(self, account_type, login, password):
        self.seen.append((account_type, login, password))
        return AuthenticationResult(account_type, self.status, f"stub {self.status.value}")


@pytest_asyncio.fixture
async def flow():
    """Dispatcher with login flow enabled, an in-memory DB, and a fake Telegram."""
    engine = create_database_engine("sqlite+aiosqlite:///:memory:")
    await initialize_database(engine)
    session_factory = create_session_factory(engine)

    session = FakeSession()
    bot = Bot(token="123:test", session=session)
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_routers(account_type_router, login_check_router)
    checker = StubChecker()
    dispatcher["login_checker"] = checker
    dispatcher["login_check_enabled"] = True
    dispatcher["session_factory"] = session_factory

    ctx = SimpleNamespace(
        dispatcher=dispatcher,
        bot=bot,
        session=session,
        checker=checker,
        session_factory=session_factory,
        storage=dispatcher.storage,
    )
    try:
        yield ctx
    finally:
        # aiogram lets a router have one parent, so detach it for the next test.
        for router in (account_type_router, login_check_router):
            router._parent_router = None
        await bot.session.close()
        await engine.dispose()


async def _state_of(ctx):
    storage_key = StorageKey(bot_id=ctx.bot.id, chat_id=USER_ID, user_id=USER_ID)
    return await ctx.storage.get_state(storage_key), await ctx.storage.get_data(storage_key)


async def _stored_batches(ctx):
    async with ctx.session_factory() as session:
        return list((await session.execute(select(CheckBatch))).scalars().all())


@pytest.mark.asyncio
async def test_full_flow_records_only_summary_and_deletes_credentials(flow, caplog):
    """Login then password: both messages are deleted, state is cleared, one summary row is saved."""
    with caplog.at_level("DEBUG"):
        await flow.dispatcher.feed_update(flow.bot, _callback_update("account_type:student", 1))
        await flow.dispatcher.feed_update(flow.bot, _message_update(LOGIN, 2))
        await flow.dispatcher.feed_update(flow.bot, _message_update(PASSWORD, 3))

    assert flow.session.called("DeleteMessage")
    assert flow.checker.seen == [(AccountType.STUDENT, LOGIN, PASSWORD)]
    assert any("stub success" in text for text in flow.session.sent_texts())

    state, data = await _state_of(flow)
    assert state is None
    assert data == {}

    batches = await _stored_batches(flow)
    assert len(batches) == 1
    assert (batches[0].total_count, batches[0].success_count) == (1, 1)

    async with flow.session_factory() as session:
        rows = list((await session.execute(select(CheckResult))).scalars().all())
    stored = repr([(r.account_label, r.status, r.account_type) for r in rows])
    assert LOGIN not in stored
    assert PASSWORD not in stored
    assert LOGIN not in caplog.text
    assert PASSWORD not in caplog.text


@pytest.mark.asyncio
async def test_password_message_is_deleted_before_check_runs(flow):
    """The password message is removed before the checker is called."""
    order = []
    original_check = flow.checker.check

    async def tracking_check(account_type, login, password):
        order.append(("check", [n for n, _ in flow.session.calls]))
        return await original_check(account_type, login, password)

    flow.checker.check = tracking_check

    await flow.dispatcher.feed_update(flow.bot, _callback_update("account_type:parent", 1))
    await flow.dispatcher.feed_update(flow.bot, _message_update(LOGIN, 2))
    await flow.dispatcher.feed_update(flow.bot, _message_update(PASSWORD, 3))

    assert order
    assert order[0][1][-1] == "DeleteMessage"


@pytest.mark.asyncio
async def test_blank_login_is_rejected_and_flow_stays_in_login_step(flow):
    """An empty login is refused without advancing to the password step."""
    await flow.dispatcher.feed_update(flow.bot, _callback_update("account_type:student", 1))
    await flow.dispatcher.feed_update(flow.bot, _message_update("   ", 2))

    state, _ = await _state_of(flow)
    assert state == LoginCheck.waiting_login.state
    assert any("1 dan 100 belgigacha" in text for text in flow.session.sent_texts())
    assert flow.checker.seen == []


@pytest.mark.asyncio
async def test_cancel_clears_state_without_checking(flow):
    """/cancel during the flow discards the login and never calls the checker."""
    await flow.dispatcher.feed_update(flow.bot, _callback_update("account_type:student", 1))
    await flow.dispatcher.feed_update(flow.bot, _message_update(LOGIN, 2))
    await flow.dispatcher.feed_update(flow.bot, _message_update("/cancel", 3))

    state, data = await _state_of(flow)
    assert state is None
    assert data == {}
    assert flow.checker.seen == []
    assert any("bekor qilindi" in text for text in flow.session.sent_texts())


@pytest.mark.asyncio
async def test_undeletable_message_asks_user_to_remove_it(flow):
    """If Telegram refuses deletion, the user is told to delete it manually."""
    flow.session.delete_fails = True

    await flow.dispatcher.feed_update(flow.bot, _callback_update("account_type:student", 1))
    await flow.dispatcher.feed_update(flow.bot, _message_update(LOGIN, 2))

    assert any("o‘zingiz o‘chirib" in text for text in flow.session.sent_texts())


@pytest.mark.asyncio
async def test_disabled_flag_keeps_unavailable_reply(flow):
    """With the flag off, selecting an account type never starts a login."""
    flow.dispatcher["login_check_enabled"] = False
    flow.dispatcher["login_checker"] = UnavailableLoginChecker()

    await flow.dispatcher.feed_update(flow.bot, _callback_update("account_type:student", 1))

    state, _ = await _state_of(flow)
    assert state is None
    assert any("mavjud emas" in text for text in flow.session.sent_texts())
    assert not flow.session.called("DeleteMessage")
