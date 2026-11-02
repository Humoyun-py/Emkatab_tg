"""Account-type selection callback handler."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from database.models import AccountType
from services.login_checker import LoginChecker
from states.login import LoginCheck


router = Router(name="account_type")

ACCOUNT_TYPE_LABELS = {
    AccountType.STUDENT.value: "Student",
    AccountType.PARENT.value: "Parent",
}


@router.callback_query(F.data.startswith("account_type:"))
async def handle_account_type_selection(
    callback: CallbackQuery,
    state: FSMContext,
    login_checker: LoginChecker,
    login_check_enabled: bool,
) -> None:
    """Start a login check when enabled, otherwise report unavailability."""

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

    if login_check_enabled:
        await state.set_data({"account_type": account_type_value})
        await state.set_state(LoginCheck.waiting_login)

        if callback.message:
            await callback.message.answer(
                f"Tanlangan akkaunt: {label}\n\n"
                "eMaktab loginingizni yuboring. "
                "Xabar tekshiruvdan so‘ng o‘chiriladi."
            )
        return

    account_type = AccountType(account_type_value)

    result = await login_checker.availability(account_type)

    if callback.message:
        await callback.message.answer(
            f"Tanlangan akkaunt: {label}\n\n"
            f"{result.message}\n\n"
            "Hozircha autentifikatsiya xizmati mavjud emas. "
            "Login va parolingizni yuborishingiz shart emas."
        )
