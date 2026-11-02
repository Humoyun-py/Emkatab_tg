"""Credential-free authentication report history handlers."""

import logging
from datetime import UTC

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from database.models import CheckBatch
from database.queries import get_user_history


logger = logging.getLogger(__name__)
router = Router(name="history")


def format_report(batch: CheckBatch) -> str:
    """Format one stored summary without account credentials or extra details."""
    created_at = batch.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)

    return (
        "eMaktab Authentication Report\n"
        f"Date: {created_at.astimezone().strftime('%Y-%m-%d %H:%M %Z')}\n"
        f"Total checked: {batch.total_count}\n"
        f"Successful: {batch.success_count}\n"
        f"Invalid credentials: {batch.invalid_count}\n"
        f"Unknown: {batch.unknown_count}"
    )


async def _load_history(
    telegram_id: int,
    session_factory: async_sessionmaker[AsyncSession],
) -> list[CheckBatch]:
    """Load recent reports in a short-lived read-only session."""
    async with session_factory() as session:
        return await get_user_history(session, telegram_id)


async def _send_history(
    *,
    telegram_id: int,
    session_factory: async_sessionmaker[AsyncSession],
    reply: Message | CallbackQuery,
) -> None:
    """Send reports belonging only to the requesting Telegram user."""
    if isinstance(reply, CallbackQuery):
        await reply.answer()

    try:
        batches = await _load_history(telegram_id, session_factory)
    except SQLAlchemyError as error:
        logger.error(
            "Could not load report history.",
            extra={"error_type": type(error).__name__},
        )
        text = "History is temporarily unavailable. Please try again later."
    else:
        text = (
            "\n\n──────────\n\n".join(format_report(batch) for batch in batches)
            if batches
            else "No saved reports yet. Reports appear here only after actual checks."
        )

    if isinstance(reply, CallbackQuery):
        if reply.message:
            await reply.message.answer(text)
    else:
        await reply.answer(text)


@router.message(Command("history"))
async def handle_history_command(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Show recent reports for the authorized command sender."""
    if message.from_user is None:
        return

    await _send_history(
        telegram_id=message.from_user.id,
        session_factory=session_factory,
        reply=message,
    )


@router.callback_query(F.data == "history")
async def handle_history_button(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Show recent reports after the user selects History."""
    if callback.from_user is None:
        await callback.answer()
        return

    await _send_history(
        telegram_id=callback.from_user.id,
        session_factory=session_factory,
        reply=callback,
    )
