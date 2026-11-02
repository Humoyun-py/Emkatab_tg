"""Main-menu inline keyboard."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Build the account-type selection menu."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Student account",
                    callback_data="account_type:student",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Parent account",
                    callback_data="account_type:parent",
                )
            ],
            [InlineKeyboardButton(text="History", callback_data="history")],
        ]
    )
