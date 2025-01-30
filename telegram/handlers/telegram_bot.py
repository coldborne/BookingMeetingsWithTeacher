import asyncio

from datetime import date, datetime, timedelta

from pytz import timezone
from sqlalchemy.orm import Session

from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup

from telegram.config.consts import URL, USERNAME, APPLE_APP_PASSWORD, SECRET_SALT, API_TOKEN
from telegram.handlers.user_data_handler import UserDataStates, UserDataHandler
from telegram.services.cal_dav_service import CalDavService
from telegram.models.database import SessionLocal
from telegram.config.logging_config import get_logger
from telegram.services.user_service import UserService
from telegram.utils.callback_data import CallbackData
from telegram.utils.menu_builder import MenuBuilder
from telegram.config.availability_days_config import AvailabilityDaysConfig

logger = get_logger(__name__)

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dispatcher = Dispatcher(storage=storage)
router = Router()

calDavService = CalDavService(URL, USERNAME, APPLE_APP_PASSWORD)
availability_days_config = AvailabilityDaysConfig()


class UserStates(StatesGroup):
    idle = State()
    selecting_date = State()
    selecting_time = State()


def get_database():
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()


@router.message(Command("start"))
async def start_command(message: types.Message, state: FSMContext, database: Session = next(get_database())):
    """
    Обрабатывает команду /start: приветствует пользователя, проверяет данные и перенаправляет на заполнение.
    """
    await message.answer("Привет! Добро пожаловать в систему бронирования.")

    user_service = UserService(database, secret_salt=SECRET_SALT)
    user_data_handler = UserDataHandler(user_service, message.from_user.id)

    user_data_handler.ensure_user_exists()

    missing_state = user_data_handler.get_missing_data_state()

    if missing_state == UserDataStates.waiting_for_name:
        await state.set_state(missing_state)
        await message.answer("Ваши данные неполные. Пожалуйста, введите ваше имя.")
    elif missing_state == UserDataStates.waiting_for_surname:
        await state.set_state(missing_state)
        await message.answer("Ваши данные неполные. Пожалуйста, введите вашу фамилию.")
    elif missing_state == UserDataStates.waiting_for_language:
        await state.set_state(missing_state)
        await message.answer(
            "Ваши данные неполные. Пожалуйста, выберите ваш язык программирования:",
            reply_markup=MenuBuilder.generate_language_keyboard()
        )
    else:
        await state.clear()
        await message.answer(
            "Все данные заполнены. Добро пожаловать в главное меню!",
            reply_markup=MenuBuilder.generate_main_menu()
        )


@router.message(UserDataStates.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext, database: Session = next(get_database())):
    """
    Обрабатывает ввод имени пользователя.
    """
    name = message.text.strip()

    if not name:
        await message.answer("Имя не может быть пустым. Пожалуйста, введите имя:")
        return

    user_service = UserService(database, secret_salt=SECRET_SALT)
    user_data_handler = UserDataHandler(user_service, message.from_user.id)
    user_data_handler.update_user_data(name=name)

    await state.set_state(UserDataStates.waiting_for_surname)
    await message.answer("Имя сохранено. Теперь введите вашу фамилию:")


@router.message(UserDataStates.waiting_for_surname)
async def process_surname(message: types.Message, state: FSMContext, database: Session = next(get_database())):
    """
    Обрабатывает ввод фамилии пользователя.
    """
    surname = message.text.strip()

    if not surname:
        await message.answer("Фамилия не может быть пустой. Пожалуйста, введите фамилию:")
        return

    user_service = UserService(database, secret_salt=SECRET_SALT)
    user_data_handler = UserDataHandler(user_service, message.from_user.id)
    user_data_handler.update_user_data(surname=surname)

    await state.set_state(UserDataStates.waiting_for_language)
    await message.answer(
        "Фамилия сохранена. Теперь выберите ваш язык программирования:",
        reply_markup=MenuBuilder.generate_language_keyboard()
    )


@router.callback_query(UserDataStates.waiting_for_language)
async def process_language(callback_query: types.CallbackQuery, state: FSMContext,
                           database: Session = next(get_database())):
    """
    Обрабатывает выбор языка программирования.
    """
    language = callback_query.data.split("_")[1]

    user_service = UserService(database, secret_salt=SECRET_SALT)
    user_data_handler = UserDataHandler(user_service, callback_query.from_user.id)
    user_data_handler.update_user_data(language=language)

    await state.clear()
    await callback_query.message.edit_text("Данные успешно сохранены! Выберите действие:")
    await bot.send_message(callback_query.from_user.id, "Выберите действие:",
                           reply_markup=MenuBuilder.generate_main_menu())


@router.callback_query(lambda c: c.data == CallbackData.BOOK_EVENT.value)
async def book_event(callback_query: types.CallbackQuery, state: FSMContext, database: Session = next(get_database())):
    """
    Обрабатывает нажатие на кнопку "Бронировать событие" и отображает календарь.
    """
    user_service = UserService(database, secret_salt=SECRET_SALT)
    user_data_handler = UserDataHandler(user_service, callback_query.from_user.id)
    user_data_handler.ensure_user_exists()

    is_missing_state = user_data_handler.get_missing_data_state()

    if is_missing_state:
        await state.set_state(is_missing_state)
        await callback_query.message.edit_text("Ваши данные неполные. Завершите их заполнение.")
        return

    today = date.today()
    keyboard = MenuBuilder.generate_calendar_keyboard(today.year, today.month)

    await callback_query.message.edit_text("Выберите дату:", reply_markup=keyboard)


@router.callback_query(lambda c: c.data.startswith(CallbackData.DATE_PREFIX.value))
async def select_date(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор даты и предлагает выбрать время.
    """
    _, year, month, day = callback_query.data.split("_")
    selected_date = date(int(year), int(month), int(day))

    today = date.today()
    start_available_date = today + timedelta(days=1)
    end_available_date = start_available_date + timedelta(days=30)

    if not (start_available_date <= selected_date <= end_available_date) or availability_days_config.is_date_blocked(
            selected_date):
        keyboard = MenuBuilder.generate_calendar_keyboard(today.year, today.month)

        await callback_query.message.edit_text(
            f"Выбранная дата ({selected_date}) недоступна. Пожалуйста, выберите актуальную дату:",
            reply_markup=keyboard
        )

        return

    await state.update_data(selected_date=str(selected_date))

    busy_hours = calDavService.parse_calendar_events(
        calDavService.get_events_time_by_date(selected_date)
    )
    keyboard = MenuBuilder.generate_hours_keyboard(busy_hours)

    await callback_query.message.edit_text(f"Вы выбрали дату: {selected_date}. Теперь выберите время:")
    await bot.send_message(callback_query.from_user.id, "Выберите время:", reply_markup=keyboard)


@router.callback_query(lambda c: c.data.startswith(CallbackData.MONTH_PREFIX.value))
async def change_month(callback_query: types.CallbackQuery):
    """
    Обрабатывает навигацию по месяцам в календаре.
    """
    _, year, month = callback_query.data.split("_")
    year, month = int(year), int(month)

    # Генерация новой клавиатуры для выбранного месяца
    keyboard = MenuBuilder.generate_calendar_keyboard(year, month)

    await callback_query.message.edit_text("Выберите дату:", reply_markup=keyboard)


@router.callback_query(lambda c: c.data.startswith(CallbackData.TIME_PREFIX.value))
async def select_time(callback_query: types.CallbackQuery, state: FSMContext, database: Session = next(get_database())):
    """
    Обрабатывает выбор времени и бронирует слот.
    """
    hour = int(callback_query.data.split("_")[1])

    user_service = UserService(database, secret_salt=SECRET_SALT)
    user = user_service.get_user_by_telegram_id(callback_query.from_user.id)

    local_tz = timezone("Europe/Moscow")
    selected_date = datetime.strptime((await state.get_data())["selected_date"], "%Y-%m-%d").date()

    start_time_local = datetime.combine(selected_date, datetime.min.time()).replace(hour=hour, tzinfo=local_tz)

    start_time = start_time_local.astimezone(timezone("UTC"))
    end_time = (start_time_local + timedelta(hours=1)).astimezone(timezone("UTC"))

    is_success = await calDavService.book_slot(
        summary=f"{user.name} {user.surname} ({user.language})",
        start=start_time,
        end=end_time
    )

    if is_success:
        busy_hours = calDavService.parse_calendar_events(
            calDavService.get_events_time_by_date(selected_date)
        )
        keyboard = MenuBuilder.generate_hours_keyboard(busy_hours)

        await callback_query.message.edit_text(
            f"Событие успешно забронировано на {selected_date} в {hour}:00.\n"
            f"Выберите следующий слот или закончите бронирование.",
            reply_markup=keyboard
        )
    else:
        await callback_query.message.edit_text(
            f"Ошибка: время {hour}:00 уже занято на {selected_date}.",
            reply_markup=callback_query.message.reply_markup
        )


@router.callback_query(lambda c: c.data == CallbackData.FINISH_BOOKING.value)
async def finish_booking(callback_query: types.CallbackQuery):
    """
    Завершает процесс бронирования и возвращает пользователя в главное меню.
    """
    await callback_query.message.edit_text(
        "Бронирование завершено. Возвращаем вас в главное меню."
    )

    await bot.send_message(
        callback_query.from_user.id,
        "Выберите действие:",
        reply_markup=MenuBuilder.generate_main_menu()
    )


async def main():
    dispatcher.include_router(router)
    logger.info('Бот запущен и готов к работе')

    await bot.delete_webhook(drop_pending_updates=True)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
