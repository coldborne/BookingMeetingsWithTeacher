from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from aiogram.dispatcher.event.bases import SkipHandler
from sqlalchemy import select

from telegram.models.database import Database
from telegram.models.models import User

database = Database()


class BanMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        telegram_id = str(event.from_user.id)

        async with database.get_session() as session:
            is_banned = await session.scalar(
                select(User.is_banned).where(User.telegram_id == telegram_id)
            ) or False  # если записи ещё нет

        if is_banned:
            text = "🚫 Бот недоступен."

            if isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=True)
            elif isinstance(event, Message):
                await event.answer(text)

            raise SkipHandler

        return await handler(event, data)
