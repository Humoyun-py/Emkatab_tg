"""Configure and run the Telegram bot."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.exceptions import TelegramAPIError
from aiogram.types import (
    CallbackQuery,
    Message,
    TelegramObject,
    User,
)
from sqlalchemy.exc import SQLAlchemyError

from config import Settings
from database.engine import (
    create_database_engine,
    create_session_factory,
    initialize_database,
)
from handlers.account_type import router as account_type_router
from handlers.history import router as history_router
from handlers.start import router as start_router


logger = logging.getLogger(__name__)


class AuthorizationMiddleware(BaseMiddleware):
    """Allow updates only from configured Telegram users."""

    def __init__(self, authorized_user_ids: frozenset[int]) -> None:
        self.authorized_user_ids = authorized_user_ids

    async def __call__(
        self,
        handler: Callable[
            [TelegramObject, dict[str, Any]],
            Awaitable[Any],
        ],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)

        if (
            not isinstance(user, User)
            or user.id not in self.authorized_user_ids
        ):
            logger.warning("Rejected update from an unauthorized user.")

            if isinstance(event, Message):
                await event.answer(
                    "Kirishga ruxsat yo‘q. "
                    "Telegram ID’ingiz AUTHORIZED_USER_IDS "
                    "sozlamasiga qo‘shilishi kerak."
                )

            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "Kirishga ruxsat yo‘q. "
                    "Bot administratoriga murojaat qiling.",
                    show_alert=True,
                )

            return None

        return await handler(event, data)


def create_dispatcher(settings: Settings) -> Dispatcher:
    """Create dispatcher and configure authorization middleware."""

    dispatcher = Dispatcher()

    dispatcher.include_routers(
        start_router,
        account_type_router,
        history_router,
    )

    authorization = AuthorizationMiddleware(
        settings.authorized_user_ids
    )

    dispatcher.message.outer_middleware(authorization)
    dispatcher.callback_query.outer_middleware(authorization)

    return dispatcher


async def main() -> None:
    """Initialize database and start Telegram polling."""

    settings = Settings.from_environment()

    bot = Bot(token=settings.bot_token)
    dispatcher = create_dispatcher(settings)
    engine = create_database_engine(settings.database_url)

    try:
        await initialize_database(engine)

        session_factory = create_session_factory(engine)
        dispatcher["session_factory"] = session_factory

        logger.info("Database initialized successfully.")
        logger.info("Starting Telegram polling.")

        await dispatcher.start_polling(bot)

    except SQLAlchemyError as error:
        logger.error(
            "Database operation failed: %s",
            type(error).__name__,
        )
        raise

    except TelegramAPIError as error:
        logger.error(
            "Telegram API operation failed: %s",
            type(error).__name__,
        )
        raise

    finally:
        await bot.session.close()
        await engine.dispose()

        logger.info("Bot resources closed.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested.")