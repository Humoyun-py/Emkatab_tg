"""Shared fakes for Telegram-level tests: a recording Bot API session and update builders.

Nothing here contacts Telegram.
"""

from aiogram.client.session.base import BaseSession
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Update


USER_ID = 111


class FakeSession(BaseSession):
    """Records Bot API calls; can simulate a message that cannot be deleted."""

    def __init__(self, delete_fails=False):
        super().__init__()
        self.calls = []
        self.delete_fails = delete_fails

    async def close(self):
        pass

    async def stream_content(self, *args, **kwargs):
        raise NotImplementedError
        yield b""

    async def make_request(self, bot, method, timeout=None):
        name = type(method).__name__
        self.calls.append((name, getattr(method, "text", None)))
        if name == "DeleteMessage" and self.delete_fails:
            raise TelegramBadRequest(method=method, message="message can't be deleted")
        if name == "SendMessage":
            return {
                "message_id": len(self.calls),
                "date": 0,
                "chat": {"id": method.chat_id, "type": "private"},
                "text": method.text,
            }
        return True

    def sent_texts(self):
        return [text for name, text in self.calls if name == "SendMessage"]

    def called(self, name):
        return any(call_name == name for call_name, _ in self.calls)


def message_update(text, update_id):
    return Update.model_validate({
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "date": 1700000000,
            "chat": {"id": USER_ID, "type": "private", "first_name": "T"},
            "from": {"id": USER_ID, "is_bot": False, "first_name": "T"},
            "text": text,
        },
    })


def callback_update(data, update_id):
    return Update.model_validate({
        "update_id": update_id,
        "callback_query": {
            "id": str(update_id),
            "from": {"id": USER_ID, "is_bot": False, "first_name": "T"},
            "chat_instance": "x",
            "data": data,
            "message": {
                "message_id": update_id,
                "date": 1700000000,
                "chat": {"id": USER_ID, "type": "private", "first_name": "T"},
                "text": "menu",
            },
        },
    })
