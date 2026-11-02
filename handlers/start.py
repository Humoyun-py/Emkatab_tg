"""Start command handler."""

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from keyboards.main import main_menu_keyboard


router = Router(name="start")


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    """Show the main menu to an authorized user."""
    await message.answer(
        "eMaktab Authentication Checker\n\nChoose an account type:",
        reply_markup=main_menu_keyboard(),
    )
