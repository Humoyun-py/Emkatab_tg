"""Conversation states for a single credential check."""

from aiogram.fsm.state import State, StatesGroup


class LoginCheck(StatesGroup):
    """Steps of one login check: login first, then password."""

    waiting_login = State()
    waiting_password = State()
