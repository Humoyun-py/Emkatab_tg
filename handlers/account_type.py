"""Account-type selection callback handler."""

from aiogram import F, Router
from aiogram.types import CallbackQuery

from database.models import AccountType
from services.login_checker import UnavailableLoginChecker


router = Router(name="account_type")

_ACCOUNT_TYPE_LABELS = {
    AccountType.STUDENT.value: "Student",
    AccountType.PARENT.value: "Parent",
}
_login_checker = UnavailableLoginChecker()


@router.callback_query(F.data.startswith("account_type:"))
async def handle_account_type_selection(callback: CallbackQuery) -> None:
    """Report that authentication is unavailable for the selected type."""
    account_type = callback.data.partition(":")[2] if callback.data else ""
    label = _ACCOUNT_TYPE_LABELS.get(account_type)
    if label is None:
        await callback.answer("Invalid account type.", show_alert=True)
        return

    await callback.answer()
    result = await _login_checker.availability(AccountType(account_type))
    if callback.message:
        await callback.message.answer(
            f"{label} account selected.\n\n"
            f"{result.message} "
            "No login or password is needed or requested."
        )
