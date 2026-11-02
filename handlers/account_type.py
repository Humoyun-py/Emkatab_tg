"""Account-type selection callback handler."""

from aiogram import F, Router
from aiogram.types import CallbackQuery

from database.models import AccountType
from services.login_checker import UnavailableLoginChecker


router = Router(name="account_type")

ACCOUNT_TYPE_LABELS = {
    AccountType.STUDENT.value: "Student",
    AccountType.PARENT.value: "Parent",
}

login_checker = UnavailableLoginChecker()


@router.callback_query(F.data.startswith("account_type:"))
async def handle_account_type_selection(
    callback: CallbackQuery,
) -> None:
    """Handle student and parent account selection."""

    account_type_value = (
        callback.data.partition(":")[2]
        if callback.data
        else ""
    )

    label = ACCOUNT_TYPE_LABELS.get(account_type_value)

    if label is None:
        await callback.answer(
            "Noto‘g‘ri akkaunt turi tanlandi.",
            show_alert=True,
        )
        return

    await callback.answer()

    account_type = AccountType(account_type_value)

    result = await login_checker.availability(account_type)

    if callback.message:
        await callback.message.answer(
            f"Tanlangan akkaunt: {label}\n\n"
            f"{result.message}\n\n"
            "Hozircha autentifikatsiya xizmati mavjud emas. "
            "Login va parolingizni yuborishingiz shart emas."
        )