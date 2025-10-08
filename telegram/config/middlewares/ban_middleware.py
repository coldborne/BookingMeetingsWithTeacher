from aiogram import BaseMiddleware
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.types import CallbackQuery
from sqlalchemy import text

from telegram.models.database import Database, logger
from telegram.utils.cryptographer import encrypt_telegram_id


class BanMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        telegram_id = encrypt_telegram_id(event.from_user.id)
        database = Database()

        async def query():
            session = await database.get_session()

            try:
                stmt = text(
                    "SELECT is_banned "
                    "FROM users "
                    "WHERE telegram_id = :telegram_id "
                    "LIMIT 1"
                )
                result = session.execute(stmt, {"telegram_id": telegram_id})
                return result.scalar()
            finally:
                await database.close_session()

        try:
            result = await database.execute_with_retry(query)
            is_banned = bool(result)
            print(is_banned)
        except Exception as exception:
            logger.error(f"❌ Не удалось проверить бан: {exception}")
            is_banned = True

        if is_banned:
            text_for_user = "🚫 Бот недоступен."

            if isinstance(event, CallbackQuery):
                await event.answer(text_for_user, show_alert=True)
            else:
                await event.answer(text_for_user)

            raise SkipHandler

        return await handler(event, data)
