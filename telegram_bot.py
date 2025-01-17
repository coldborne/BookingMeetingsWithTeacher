import asyncio
import logging
from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import date
from sqlalchemy.orm import Session

from consts import URL, USERNAME, APPLE_APP_PASSWORD, SECRET_SALT, API_TOKEN
from cal_dav_service import CalDavService
from database import SessionLocal
from user_service import UserService

# Логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Инициализация бота и маршрутов
bot = Bot(token=API_TOKEN)
dispatcher = Dispatcher()
router = Router()

# Инициализация CalDavService
calDavService = CalDavService(URL, USERNAME, APPLE_APP_PASSWORD)


# Создание сессии базы данных
def get_database():
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()


def generate_main_menu():
    logger.info("Отображение главного меню")
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Бронировать событие", callback_data="book_event")],
            [InlineKeyboardButton(text="Изменить данные", callback_data="update_data")],
        ]
    )
    return keyboard


async def ensure_user_data_integrity(user_service, telegram_id):
    """Проверяет, заполнены ли все данные пользователя. Возвращает False, если данные неполные."""
    user = user_service.get_user_by_telegram_id(telegram_id)

    if not user:
        logger.warning(f"Пользователь {telegram_id} не найден. Создание нового пользователя.")
        user = user_service.create_user(telegram_id)

    if not user.name:
        user_service.set_user_state(user.telegram_id, "waiting_for_name")
        await bot.send_message(telegram_id, "Ваши данные неполные. Введите имя:")
        return False

    if not user.surname:
        user_service.set_user_state(user.telegram_id, "waiting_for_surname")
        await bot.send_message(telegram_id, "Ваши данные неполные. Введите фамилию:")
        return False

    if not user.language:
        user_service.set_user_state(user.telegram_id, "waiting_for_language")
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Python", callback_data="language_python"),
                 InlineKeyboardButton(text="C#", callback_data="language_csharp")]
            ]
        )
        await bot.send_message(telegram_id, "Ваши данные неполные. Выберите язык программирования:",
                               reply_markup=keyboard)
        return False

    return True


@router.callback_query(lambda c: c.data == "book_event")
async def book_event(callback_query: types.CallbackQuery, database: Session = next(get_database())):
    user_service = UserService(database, secret_salt=SECRET_SALT)

    if not await ensure_user_data_integrity(user_service, callback_query.from_user.id):
        return

    today = date.today()
    keyboard = generate_calendar_keyboard(today.year, today.month)
    logger.info(f"Пользователь {callback_query.from_user.id} выбрал бронирование события")

    await callback_query.message.edit_text("Выберите дату:", reply_markup=keyboard)


@router.callback_query(lambda c: c.data == "update_data")
async def update_data(callback_query: types.CallbackQuery, database: Session = next(get_database())):
    user_service = UserService(database, secret_salt=SECRET_SALT)
    user_service.set_user_state(callback_query.from_user.id, "waiting_for_name")

    logger.info(f"Пользователь {callback_query.from_user.id} выбрал обновление данных")

    await callback_query.message.edit_text("Введите имя:")


def generate_hours_keyboard(events):
    hours = range(10, 18)
    buttons = []

    for hour in hours:
        time_str = f"{hour}:00"
        button_text = f"🟢 {time_str}" if hour not in events else f"🔴 {time_str}"
        callback_data = f"time_{hour}" if hour not in events else "disabled"

        buttons.append(InlineKeyboardButton(text=button_text, callback_data=callback_data))

    inline_keyboard = [buttons[i:i + 4] for i in range(0, len(buttons), 4)]

    inline_keyboard.append(
        [InlineKeyboardButton(text="Закончить бронирование на этот день", callback_data="finish_booking")]
    )

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def generate_calendar_keyboard(year, month):
    from calendar import monthrange

    days_of_week = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    inline_keyboard = []

    inline_keyboard.append([InlineKeyboardButton(text=day, callback_data="ignore") for day in days_of_week])

    _, days_in_month = monthrange(year, month)
    first_day = date(year, month, 1).weekday()

    buttons = [InlineKeyboardButton(text=" ", callback_data="ignore")] * first_day

    for day in range(1, days_in_month + 1):
        buttons.append(InlineKeyboardButton(text=str(day), callback_data=f"date_{year}_{month}_{day}"))

    for i in range(0, len(buttons), 7):
        inline_keyboard.append(buttons[i:i + 7])

    prev_month = (month - 1) if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = (month + 1) if month < 12 else 1
    next_year = year if month < 12 else year + 1

    inline_keyboard.append([
        InlineKeyboardButton(text="⬅️", callback_data=f"month_{prev_year}_{prev_month}"),
        InlineKeyboardButton(text=f"{year}-{month:02}", callback_data="ignore"),
        InlineKeyboardButton(text="➡️", callback_data=f"month_{next_year}_{next_month}")
    ])

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


@router.message(Command("start"))
async def start_command(message: types.Message, database: Session = next(get_database())):
    user_service = UserService(database, secret_salt=SECRET_SALT)
    if not await ensure_user_data_integrity(user_service, message.from_user.id):
        return

    logger.info(f"Пользователь {message.from_user.id} начал взаимодействие с ботом")
    await message.answer("Добро пожаловать в систему бронирования!", reply_markup=generate_main_menu())


@router.message(lambda message: UserService(next(get_database()), secret_salt=SECRET_SALT).get_user_state(
    message.from_user.id) == "waiting_for_name")
async def process_name(message: types.Message, database: Session = next(get_database())):
    user_service = UserService(database, secret_salt=SECRET_SALT)
    user_service.update_user(message.from_user.id, name=message.text, state=None)
    logger.info(f"Пользователь {message.from_user.id} ввел имя: {message.text}")

    if not await ensure_user_data_integrity(user_service, message.from_user.id):
        return

    await message.answer("Ваши данные успешно сохранены!", reply_markup=generate_main_menu())


@router.message(lambda message: UserService(next(get_database()), secret_salt=SECRET_SALT).get_user_state(
    message.from_user.id) == "waiting_for_surname")
async def process_surname(message: types.Message, database: Session = next(get_database())):
    user_service = UserService(database, secret_salt=SECRET_SALT)
    user_service.update_user(message.from_user.id, surname=message.text, state=None)
    logger.info(f"Пользователь {message.from_user.id} ввел фамилию: {message.text}")

    if not await ensure_user_data_integrity(user_service, message.from_user.id):
        return

    await message.answer("Ваши данные успешно сохранены!", reply_markup=generate_main_menu())


@router.callback_query(lambda c: c.data.startswith("language"))
async def process_language(callback_query: types.CallbackQuery, database: Session = next(get_database())):
    language = callback_query.data.split("_")[1]
    user_service = UserService(database, secret_salt=SECRET_SALT)
    user_service.update_user(callback_query.from_user.id, language=language, state=None)
    logger.info(f"Пользователь {callback_query.from_user.id} выбрал язык: {language}")

    if not await ensure_user_data_integrity(user_service, callback_query.from_user.id):
        return

    await callback_query.message.edit_text("Ваши данные успешно сохранены!")
    await bot.send_message(callback_query.from_user.id, "Выберите действие:", reply_markup=generate_main_menu())


async def main():
    dispatcher.include_router(router)

    logger.info("Бот запущен и готов к работе")

    await bot.delete_webhook(drop_pending_updates=True)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
