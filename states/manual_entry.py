"""Conversation state for entering counts of outcomes checked outside the bot."""

from aiogram.fsm.state import State, StatesGroup


class ManualEntry(StatesGroup):
    """Waiting for one line of counts from the operator."""

    waiting_counts = State()
