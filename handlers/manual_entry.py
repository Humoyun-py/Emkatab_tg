"""Manual entry of check outcomes that an operator counted outside the bot.

The bot never contacts eMaktab here and never asks for credentials. It stores
only the counts the operator typed, as anonymous rows with the label
"manual entry".
"""

import logging
import re
from dataclasses import dataclass

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from database.models import AccountType, CheckStatus
from database.queries import CheckResultInput, get_or_create_user, record_check_batch
from states.manual_entry import ManualEntry


logger = logging.getLogger(__name__)
router = Router(name="manual_entry")

MAX_COUNT = 1000
_WHOLE_NUMBER = re.compile(r"[0-9]+")
USAGE = (
    "Format: akkaunt muvaffaqiyatli noto‘g‘ri noaniq\n"
    "Masalan: student 3 1 0\n\n"
    "Bekor qilish uchun /cancel."
)


@dataclass(frozen=True, slots=True)
class ManualCounts:
    """Validated counts for one manual batch."""

    account_type: AccountType
    success: int
    invalid: int
    unknown: int

    @property
    def total(self) -> int:
        return self.success + self.invalid + self.unknown


def parse_manual_counts(text: str) -> ManualCounts:
    """Parse 'student 3 1 0' into validated counts; raise ValueError otherwise."""
    parts = text.split()
    if len(parts) != 4:
        raise ValueError("To‘rtta qiymat kerak: akkaunt va uchta son.")

    try:
        account_type = AccountType(parts[0].lower())
    except ValueError as error:
        raise ValueError("Akkaunt turi student yoki parent bo‘lishi kerak.") from error

    numbers = parts[1:]
    if not all(_WHOLE_NUMBER.fullmatch(value) for value in numbers):
        raise ValueError("Sonlar faqat butun musbat raqamlardan iborat bo‘lishi kerak.")

    success, invalid, unknown = (int(value) for value in numbers)
    if max(success, invalid, unknown) > MAX_COUNT:
        raise ValueError(f"Har bir son {MAX_COUNT} dan oshmasligi kerak.")

    counts = ManualCounts(account_type, success, invalid, unknown)
    if counts.total == 0:
        raise ValueError("Kamida bitta natija kiriting.")
    return counts


def _results_for(counts: ManualCounts) -> list[CheckResultInput]:
    """Expand counts into one anonymous result row per check."""
    statuses = (
        [CheckStatus.SUCCESS] * counts.success
        + [CheckStatus.INVALID_CREDENTIALS] * counts.invalid
        + [CheckStatus.UNKNOWN] * counts.unknown
    )
    return [
        CheckResultInput(
            account_type=counts.account_type,
            account_label="manual entry",
            status=status,
        )
        for status in statuses
    ]


@router.callback_query(F.data == "manual_entry")
async def handle_manual_entry_button(callback: CallbackQuery, state: FSMContext) -> None:
    """Ask the operator for one line of counts."""
    await callback.answer()
    await state.set_state(ManualEntry.waiting_counts)
    if callback.message:
        await callback.message.answer(USAGE)


@router.message(Command("cancel"), StateFilter(ManualEntry))
async def handle_manual_cancel(message: Message, state: FSMContext) -> None:
    """Abort an unfinished manual entry."""
    await state.clear()
    await message.answer("Kiritish bekor qilindi.")


@router.message(ManualEntry.waiting_counts, F.text)
async def handle_manual_counts(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Validate the counts, save them as one batch, and confirm."""
    try:
        counts = parse_manual_counts(message.text or "")
    except ValueError as error:
        await message.answer(f"{error}\n\n{USAGE}")
        return

    await state.clear()

    if message.from_user is None:
        return

    try:
        async with session_factory.begin() as session:
            user = await get_or_create_user(session, message.from_user.id)
            await record_check_batch(
                session,
                user_id=user.id,
                results=_results_for(counts),
            )
    except SQLAlchemyError as error:
        logger.error(
            "Could not save manual entry.",
            extra={"error_type": type(error).__name__},
        )
        await message.answer("Natija saqlanmadi. Keyinroq qayta urinib ko‘ring.")
        return

    await message.answer(
        f"Saqlandi ({counts.account_type.value}): jami {counts.total}, "
        f"muvaffaqiyatli {counts.success}, noto‘g‘ri {counts.invalid}, "
        f"noaniq {counts.unknown}."
    )
