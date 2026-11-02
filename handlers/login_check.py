"""Login and password steps for one eMaktab credential check.

Credentials exist only in local variables for the duration of one check:
the FSM state is cleared before the network call, the Telegram message
holding each value is deleted, and nothing here logs or stores them.
"""

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from database.models import AccountType, CheckStatus
from database.queries import CheckResultInput, get_or_create_user, record_check_batch
from handlers.account_type import ACCOUNT_TYPE_LABELS
from services.login_checker import LoginChecker
from states.login import LoginCheck


logger = logging.getLogger(__name__)
router = Router(name="login_check")

_MAX_LOGIN_LENGTH = 100


async def _delete_sensitive_message(message: Message) -> None:
    """Remove a message that contains a login or password."""
    try:
        await message.delete()
    except TelegramAPIError as error:
        logger.warning(
            "Could not delete a sensitive message.",
            extra={"error_type": type(error).__name__},
        )
        await message.answer(
            "Xabarni o‘chirib bo‘lmadi. Iltimos, uni o‘zingiz o‘chirib tashlang."
        )


@router.message(Command("cancel"), StateFilter(LoginCheck))
async def handle_cancel(message: Message, state: FSMContext) -> None:
    """Abort an unfinished login check."""
    await state.clear()
    await message.answer("Tekshiruv bekor qilindi.")


@router.message(LoginCheck.waiting_login, F.text)
async def handle_login_input(message: Message, state: FSMContext) -> None:
    """Keep the login for the next step and remove its message."""
    login = (message.text or "").strip()
    await _delete_sensitive_message(message)

    if not login or len(login) > _MAX_LOGIN_LENGTH:
        await message.answer(
            f"Login 1 dan {_MAX_LOGIN_LENGTH} belgigacha bo‘lishi kerak. "
            "Qayta yuboring."
        )
        return

    await state.update_data(login=login)
    await state.set_state(LoginCheck.waiting_password)
    await message.answer("Endi parolni yuboring. Xabar darhol o‘chiriladi.")


@router.message(LoginCheck.waiting_password, F.text)
async def handle_password_input(
    message: Message,
    state: FSMContext,
    login_checker: LoginChecker,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Run the check once, record only its outcome, and reply."""
    password = message.text or ""
    await _delete_sensitive_message(message)

    data = await state.get_data()
    # Clear state before the network call so credentials are not kept if it fails.
    await state.clear()

    account_type = AccountType(data["account_type"])
    label = ACCOUNT_TYPE_LABELS[account_type.value]
    login = data.get("login", "")

    result = await login_checker.check(account_type, login, password)
    del login, password

    logger.info(
        "Login check finished.",
        extra={"account_type": account_type.value, "status": result.status.value},
    )

    saved = await _record_outcome(message, session_factory, account_type, label, result.status)
    note = "" if saved else "\n\nNatija saqlanmadi. Keyinroq qayta urinib ko‘ring."
    await message.answer(f"{label} akkaunt: {result.message}{note}")


async def _record_outcome(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
    account_type: AccountType,
    label: str,
    status: CheckStatus,
) -> bool:
    """Save one summary row. Returns False if the database rejected it."""
    if message.from_user is None:
        return False

    try:
        async with session_factory.begin() as session:
            user = await get_or_create_user(session, message.from_user.id)
            await record_check_batch(
                session,
                user_id=user.id,
                results=[
                    CheckResultInput(
                        account_type=account_type,
                        account_label=f"{label} account",
                        status=status,
                    )
                ],
            )
    except SQLAlchemyError as error:
        logger.error(
            "Could not save check result.",
            extra={"error_type": type(error).__name__},
        )
        return False
    return True
