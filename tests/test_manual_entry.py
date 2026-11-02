"""Tests for manual entry of operator-counted check outcomes."""

from types import SimpleNamespace

import pytest
import pytest_asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy import select

from database.engine import create_database_engine, create_session_factory, initialize_database
from database.models import AccountType, CheckBatch, CheckResult, CheckStatus
from handlers.manual_entry import MAX_COUNT, parse_manual_counts, router as manual_entry_router
from states.manual_entry import ManualEntry
from tests.telegram_fakes import USER_ID, FakeSession, callback_update, message_update


# --- parsing -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("student 3 1 0", (AccountType.STUDENT, 3, 1, 0)),
        ("PARENT 0 0 1", (AccountType.PARENT, 0, 0, 1)),
        ("  parent   2  2  2 ", (AccountType.PARENT, 2, 2, 2)),
    ],
)
def test_valid_lines_are_parsed(text, expected):
    """Account type and three counts are read in order."""
    counts = parse_manual_counts(text)

    assert (counts.account_type, counts.success, counts.invalid, counts.unknown) == expected
    assert counts.total == sum(expected[1:])


@pytest.mark.parametrize(
    "text",
    [
        "",
        "student 1 2",
        "student 1 2 3 4",
        "teacher 1 1 1",
        "student -1 0 0",
        "student +2 0 0",
        "student 1.5 0 0",
        "student 1_0 0 0",
        "student ١ 0 0",
        "student 0 0 0",
        f"student {MAX_COUNT + 1} 0 0",
    ],
)
def test_invalid_lines_are_rejected(text):
    """Malformed, negative, non-ASCII, zero-total, or oversized input is refused."""
    with pytest.raises(ValueError):
        parse_manual_counts(text)


# --- Telegram flow -----------------------------------------------------------


@pytest_asyncio.fixture
async def flow():
    """Dispatcher with the manual-entry router and an in-memory database."""
    engine = create_database_engine("sqlite+aiosqlite:///:memory:")
    await initialize_database(engine)
    session_factory = create_session_factory(engine)

    session = FakeSession()
    bot = Bot(token="123:test", session=session)
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_routers(manual_entry_router)
    dispatcher["session_factory"] = session_factory

    ctx = SimpleNamespace(
        dispatcher=dispatcher,
        bot=bot,
        session=session,
        session_factory=session_factory,
        storage=dispatcher.storage,
    )
    try:
        yield ctx
    finally:
        # aiogram lets a router have one parent, so detach it for the next test.
        manual_entry_router._parent_router = None
        await bot.session.close()
        await engine.dispose()


async def _state(ctx):
    key = StorageKey(bot_id=ctx.bot.id, chat_id=USER_ID, user_id=USER_ID)
    return await ctx.storage.get_state(key)


async def _start_entry(ctx):
    await ctx.dispatcher.feed_update(ctx.bot, callback_update("manual_entry", 1))


@pytest.mark.asyncio
async def test_button_starts_entry_and_saves_one_batch(flow):
    """Counts are stored as one batch with matching totals and no personal data."""
    await _start_entry(flow)
    assert await _state(flow) == ManualEntry.waiting_counts.state

    await flow.dispatcher.feed_update(flow.bot, message_update("student 2 1 0", 2))

    assert await _state(flow) is None
    assert any("jami 3" in (text or "") for text in flow.session.sent_texts())

    async with flow.session_factory() as session:
        batches = list((await session.execute(select(CheckBatch))).scalars().all())
        rows = list((await session.execute(select(CheckResult))).scalars().all())

    assert len(batches) == 1
    assert (batches[0].total_count, batches[0].success_count,
            batches[0].invalid_count, batches[0].unknown_count) == (3, 2, 1, 0)
    assert len(rows) == 3
    assert {row.account_label for row in rows} == {"manual entry"}
    assert sorted(row.status for row in rows) == sorted(
        [CheckStatus.SUCCESS, CheckStatus.SUCCESS, CheckStatus.INVALID_CREDENTIALS]
    )


@pytest.mark.asyncio
async def test_invalid_line_keeps_waiting_and_shows_usage(flow):
    """A bad line is refused, the operator stays in the entry step, and the format is shown."""
    await _start_entry(flow)
    await flow.dispatcher.feed_update(flow.bot, message_update("student x 1 1", 2))

    assert await _state(flow) == ManualEntry.waiting_counts.state
    texts = [text or "" for text in flow.session.sent_texts()]
    assert any("butun" in text for text in texts)
    assert any("Masalan: student 3 1 0" in text for text in texts)

    async with flow.session_factory() as session:
        assert list((await session.execute(select(CheckBatch))).scalars().all()) == []


@pytest.mark.asyncio
async def test_cancel_discards_the_entry(flow):
    """/cancel leaves the entry step without saving anything."""
    await _start_entry(flow)
    await flow.dispatcher.feed_update(flow.bot, message_update("/cancel", 2))

    assert await _state(flow) is None
    async with flow.session_factory() as session:
        assert list((await session.execute(select(CheckBatch))).scalars().all()) == []


@pytest.mark.asyncio
async def test_text_outside_entry_is_ignored(flow):
    """Without the entry state, a count-looking message does nothing."""
    await flow.dispatcher.feed_update(flow.bot, message_update("student 1 0 0", 2))

    assert flow.session.calls == []
