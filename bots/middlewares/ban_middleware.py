from aiogram import BaseMiddleware
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.types import CallbackQuery

from bots.config.logging_config import get_logger
from bots.config.platforms import Platforms
from bots.models.database import Database
from bots.services.identity_service import IdentityService
from bots.services.user_service import UserService

logger = get_logger(__name__)


class BanMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        database = Database()
        user_service = UserService(database)
        identity_service = IdentityService(database, user_service)

        try:
            user = await identity_service.get_user_by_identity(
                Platforms.TELEGRAM,
                str(event.from_user.id),
            )
        except Exception as exception:
            logger.error(f"❌ Не удалось проверить бан: {exception}")
            user = None

        if user and user.is_banned:
            text_for_user = "🚫 Бот недоступен."

            if isinstance(event, CallbackQuery):
                await event.answer(text_for_user, show_alert=True)
            else:
                await event.answer(text_for_user)

            raise SkipHandler

        return await handler(event, data)
