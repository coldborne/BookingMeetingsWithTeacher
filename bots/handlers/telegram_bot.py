import asyncio
from asyncio import Lock
from collections import defaultdict
from datetime import date, datetime, timedelta
from functools import wraps

from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from pytz import timezone

from bots.config.availability_days_config import AvailabilityDaysConfig
from bots.config.consts import (ADMIN_TELEGRAM_ID, API_TOKEN,
                                APPLE_APP_PASSWORD, URL, USERNAME)
from bots.config.logging_config import get_logger
from bots.config.platforms import Platforms
from bots.middlewares.ban_middleware import BanMiddleware
from bots.handlers.user_data_handler import UserDataHandler, UserDataStates
from bots.models.database import Database
from bots.models.models import User
from bots.services.cal_dav_service import CalDavService
from bots.services.user_service import UserService
from bots.services.identity_service import IdentityService
from bots.services.session_service import SessionService
from bots.utils.callback_data import CallbackData
from bots.utils.cryptographer import decrypt_telegram_id
from bots.utils.main import is_date_available

from bots.platforms.telegram.menu_builder import MenuBuilder

logger = get_logger(__name__)

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dispatcher = Dispatcher(storage=storage)

dispatcher.message.middleware(BanMiddleware())
dispatcher.callback_query.middleware(BanMiddleware())

router = Router()

user_task_locks = defaultdict(Lock)
user_tasks = defaultdict(set)

calDavService = CalDavService(URL, USERNAME, APPLE_APP_PASSWORD)
availability_days_config = AvailabilityDaysConfig()

database = Database()
asyncio.run(database.connect())

user_service = UserService(database)
identity_service = IdentityService(database, user_service)
session_service = SessionService(database)


class UserStates(StatesGroup):
    idle = State()
    selecting_date = State()
    selecting_time = State()


def task_handler(task_key_func=None):
    """
    Декоратор для управления задачами пользователя.
    task_key_func: Функция, которая возвращает уникальный ключ задачи (по умолчанию ID пользователя и имя функции).
    """

    def decorator(handler):
        @wraps(handler)
        async def wrapper(*args, **kwargs):
            event = args[0]
            user_id = (
                event.from_user.id
                if isinstance(event, types.CallbackQuery) or isinstance(event, types.Message)
                else None
            )

            task_key = task_key_func(event, *args, **kwargs) if task_key_func else f"{user_id}_{handler.__name__}"

            if task_key in user_tasks[user_id]:
                logger.warning(f"Пользователь {user_id} уже выполняет задачу {task_key}. Игнорируем повторный запрос.")
                return

            user_tasks[user_id].add(task_key)

            async with user_task_locks[user_id]:
                try:
                    return await handler(*args, **kwargs)
                finally:
                    user_tasks[user_id].remove(task_key)

        return wrapper

    return decorator


@router.message(Command("start"))
@task_handler(task_key_func=lambda event, *args, **kwargs: f"{event.from_user.id}_start")
async def start_command(message: types.Message, state: FSMContext):
    await message.answer("Привет! Добро пожаловать в систему бронирования.")
    await message.answer(
        "ВАЖНО! Перед работой с ботом прочитайте подробности работы с ботом через команду /help. "
        "При продолжении работы с ботом вы автоматически подтверждаете согласие с данными подробностями"
    )

    user = await identity_service.get_or_create_user_by_identity(
        Platforms.TELEGRAM,
        str(message.from_user.id),
    )

    if not user:
        await message.answer("❌ Не удалось инициализировать пользователя. Попробуйте позже.")
        return

    user_data_handler = UserDataHandler(user_service, user.id)
    await user_data_handler.ensure_user_exists()

    missing_state, _, _ = await user_data_handler.get_missing_data_state()

    if missing_state == UserDataStates.WAITING_FOR_NAME:
        await state.set_state(missing_state)
        await session_service.set_state(user.id, Platforms.TELEGRAM, "WAITING_FOR_NAME", {})
        await message.answer("Ваши данные неполные. Пожалуйста, введите ваше имя.")
    elif missing_state == UserDataStates.WAITING_FOR_SURNAME:
        await state.set_state(missing_state)
        await session_service.set_state(user.id, Platforms.TELEGRAM, "WAITING_FOR_SURNAME", {})
        await message.answer("Ваши данные неполные. Пожалуйста, введите вашу фамилию.")
    elif missing_state == UserDataStates.WAITING_FOR_LANGUAGE:
        await state.set_state(missing_state)
        await session_service.set_state(user.id, Platforms.TELEGRAM, "WAITING_FOR_LANGUAGE", {})
        await message.answer(
            "Ваши данные неполные. Пожалуйста, выберите ваш язык программирования:",
            reply_markup=MenuBuilder.generate_language_keyboard(),
        )
    else:
        await state.clear()
        await session_service.clear_state(user.id, Platforms.TELEGRAM)
        await message.answer(
            "Все данные заполнены. Добро пожаловать в главное меню!",
            reply_markup=MenuBuilder.generate_main_menu(),
        )


@router.message(Command("help"))
async def help_command(message: types.Message):
    """
    Обрабатывает команду /help и выводит справочную информацию о работе бота.
    """
    help_text = (
        "ℹ️ *Помощь по боту бронирования занятий*\n\n"
        "📌 *Доступные команды:*\n"
        "  `/start` \\- Начать работу с ботом\n"
        "  `/help` \\- Получить справочную информацию\n"
        "  `/change_data` или пункт меню 'Изменить данные' \\- Изменить свои данные\n\n"
        "🗓 *Как работает бронирование?*\n"
        "1️⃣ Выберите доступную дату в календаре\\. НЕдоступные даты отмечаются знаком ❌, их выбор недоступен\\.\n"
        "2️⃣ Выберите удобное время для занятия\\. Доступные часы отмечены \\- 🟢, недоступные \\- 🔴\\.\n"
        "3️⃣ Подтвердите окончание бронирования на выбранный день\\.\n\n"
        "⏰ *Важная информация:*\n"
        "  \\- Все временные слоты отображаются по *Московскому времени \\(UTC\\+3\\)*\\.\n"
        "  \\- Бронирование доступно не более чем на *30 дней вперёд*\\.\n"
        "  \\- Если у вас неполные данные профиля, бот запросит их перед бронированием\\.\n"
        "      Вам требуется заполнить ваши РЕАЛЬНЫЕ: имя, фамилия и ЯП\\.\n"
        "      Если введенные данные будут не совпадать с вашими реальными данными, "
        "то администратор имеет право считать запись недействительной\\.\n"
        "  \\- На данный момент бот находится на стадии MVP, если вы обнаружили баги или недочёты, сообщите о них, пожалуйста, администратору\\.\n"
        "  \\- Если у вас есть предложения по новому функционалу, также просьба написать с этими предложениями администратору\\.\n\n"
        "💡 *Дополнительные возможности:*\n"
        "  \\- Вы можете изменить свои данные в любое время через команду `/change_data`\\.\n"
        "  \\- После успешного бронирования можно выбрать дополнительные слоты на выбранный день\\.\n"
        "  \\- Чтобы завершить процесс бронирования на выбранный день, нажмите *Закончить бронирование на этот день*\\.\n\n"
        "🔧 Если у вас возникли проблемы с ботом, обратитесь к администратору\\."
    )

    await message.answer(help_text, parse_mode="MarkdownV2")


@router.message(Command(str(CallbackData.UPDATE_DATA.value)))
@router.callback_query(lambda c: c.data == "change_data")
async def change_data_command(event: types.Message | types.CallbackQuery, state: FSMContext):
    platform_user_id = str(event.from_user.id)
    user = await identity_service.get_or_create_user_by_identity(Platforms.TELEGRAM, platform_user_id)

    if not user:
        if isinstance(event, types.Message):
            await event.answer("❌ Не удалось инициализировать пользователя.")
        else:
            await event.message.edit_text("❌ Не удалось инициализировать пользователя.")
        return

    await state.update_data(new_name=None, new_surname=None, new_language=None)
    await state.set_state(UserDataStates.WAITING_FOR_NAME)
    await session_service.set_state(user.id, Platforms.TELEGRAM, "WAITING_FOR_NAME", {})

    if isinstance(event, types.Message):
        await event.answer("Введите ваше новое имя:")
    elif isinstance(event, types.CallbackQuery):
        await event.message.edit_text("Введите ваше новое имя:")


@router.message(UserDataStates.WAITING_FOR_NAME)
async def process_name(message: types.Message, state: FSMContext):
    """
    Обрабатывает ввод имени пользователя.
    """
    name = message.text.strip()

    if not name:
        await message.answer("Имя не может быть пустым. Пожалуйста, введите имя:")
        return

    await state.update_data(new_name=name)
    await state.set_state(UserDataStates.WAITING_FOR_SURNAME)
    await message.answer("Имя сохранено. Теперь введите вашу фамилию:")


@router.message(UserDataStates.WAITING_FOR_SURNAME)
async def process_surname(message: types.Message, state: FSMContext):
    """
    Обрабатывает ввод фамилии пользователя.
    """
    surname = message.text.strip()

    if not surname:
        await message.answer("Фамилия не может быть пустой. Пожалуйста, введите фамилию:")
        return

    await state.update_data(new_surname=surname)
    await state.set_state(UserDataStates.WAITING_FOR_LANGUAGE)
    await message.answer(
        "Фамилия сохранена. Теперь выберите ваш язык программирования:",
        reply_markup=MenuBuilder.generate_language_keyboard()
    )


@router.callback_query(UserDataStates.WAITING_FOR_LANGUAGE)
async def process_language(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор языка программирования.
    """
    language = callback_query.data.split("_")[1]
    await state.update_data(new_language=language)

    user_data = await state.get_data()
    name, surname, language = user_data["new_name"], user_data["new_surname"], user_data["new_language"]

    confirm_keyboard = MenuBuilder.generate_confirmation_keyboard()

    await state.set_state(UserDataStates.CONFIRMING_CHANGES)
    await callback_query.message.edit_text(
        f"Вы ввели следующие данные:\n\n"
        f"📝 Имя: {name}\n"
        f"📝 Фамилия: {surname}\n"
        f"📝 Язык программирования: {language}\n\n"
        f"Вы уверены, что хотите сохранить эти данные?",
        reply_markup=confirm_keyboard
    )


@router.callback_query(lambda c: c.data == "confirm_changes", UserDataStates.CONFIRMING_CHANGES)
async def confirm_changes(callback_query: types.CallbackQuery, state: FSMContext):
    user = await identity_service.get_user_by_identity(
        Platforms.TELEGRAM,
        str(callback_query.from_user.id),
    )

    if not user:
        await callback_query.message.edit_text("❌ Пользователь не найден.")
        return

    user_data = await state.get_data()
    name = user_data["new_name"]
    surname = user_data["new_surname"]
    language = user_data["new_language"]

    await user_service.update_user_by_id(
        user.id,
        name=name,
        surname=surname,
        language=language,
    )

    await state.clear()
    await session_service.clear_state(user.id, Platforms.TELEGRAM)

    await callback_query.message.edit_text(
        "✅ Данные успешно обновлены! Выберите действие:",
        reply_markup=MenuBuilder.generate_main_menu(),
    )


@router.callback_query(lambda c: c.data == "reject_changes", UserDataStates.CONFIRMING_CHANGES)
async def reject_changes(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Отклоняет изменения и возвращает пользователя к вводу имени.
    """
    await state.set_state(UserDataStates.WAITING_FOR_NAME)
    await callback_query.message.edit_text("❌ Изменение данных отменено. Введите ваше новое имя:")


@router.callback_query(lambda c: c.data == CallbackData.BOOK_EVENT.value)
async def book_event(callback_query: types.CallbackQuery, state: FSMContext):
    user = await identity_service.get_or_create_user_by_identity(
        Platforms.TELEGRAM,
        str(callback_query.from_user.id),
    )

    if not user:
        await callback_query.message.edit_text("❌ Не удалось инициализировать пользователя.")
        return

    user_data_handler = UserDataHandler(user_service, user.id)
    await user_data_handler.ensure_user_exists()

    missing_state, _, first_missing_label = await user_data_handler.get_missing_data_state()

    if missing_state:
        await state.set_state(missing_state)
        await session_service.set_state(user.id, Platforms.TELEGRAM, str(missing_state), {})
        await callback_query.message.edit_text(
            f"❌ Ваши данные неполные. Завершите их заполнение.\n"
            f"✍️ Введите: {first_missing_label}."
        )
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

    if is_date_available(selected_date, today):
        keyboard = MenuBuilder.generate_calendar_keyboard(today.year, today.month)

        await callback_query.message.edit_text(
            f"Выбранная дата ({selected_date}) недоступна. Пожалуйста, выберите актуальную дату:",
            reply_markup=keyboard
        )

        return

    await state.update_data(selected_date=str(selected_date))

    user = await identity_service.get_user_by_identity(
        Platforms.TELEGRAM,
        str(callback_query.from_user.id),
    )

    if user:
        await session_service.set_state(
            user.id,
            Platforms.TELEGRAM,
            "SELECTING_TIME",
            {"selected_date": str(selected_date)},
        )

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
@task_handler(task_key_func=lambda event, *args, **kwargs: f"{event.from_user.id}_{event.data}")
async def select_time(callback_query: types.CallbackQuery, state: FSMContext):
    hour = int(callback_query.data.split("_")[1])

    user = await identity_service.get_user_by_identity(
        Platforms.TELEGRAM,
        str(callback_query.from_user.id),
    )

    if not user:
        await callback_query.message.edit_text("❌ Пользователь не найден.")
        return

    local_tz = timezone("Europe/Moscow")

    session_payload = await session_service.get_payload(user.id, Platforms.TELEGRAM)
    selected_date_raw = session_payload.get("selected_date")

    if not selected_date_raw:
        fallback_state_data = await state.get_data()
        selected_date_raw = fallback_state_data.get("selected_date")

    if not selected_date_raw:
        await callback_query.message.edit_text("❌ Не выбрана дата. Начните бронирование заново.")
        return

    selected_date = datetime.strptime(selected_date_raw, "%Y-%m-%d").date()

    start_time_local = local_tz.localize(datetime.combine(selected_date, datetime.min.time().replace(hour=hour)))
    start_time = start_time_local.astimezone(timezone("UTC"))
    end_time = (start_time_local + timedelta(hours=1)).astimezone(timezone("UTC"))

    is_success = await calDavService.book_slot(
        summary=f"{user.name} {user.surname} {user.hour_rate} ({user.language})",
        start=start_time,
        end=end_time,
    )

    busy_hours = calDavService.parse_calendar_events(
        calDavService.get_events_time_by_date(selected_date)
    )
    keyboard = MenuBuilder.generate_hours_keyboard(busy_hours)

    if is_success:
        await callback_query.message.answer(
            f"✅ Событие успешно забронировано на {selected_date} в {hour}:00.\n"
            f"Выберите следующий слот или закончите бронирование."
        )
        await callback_query.message.edit_text(
            "Выберите время:",
            reply_markup=keyboard,
        )
    else:
        await callback_query.message.edit_text(
            f"Ошибка: время {hour}:00 уже занято на {selected_date}.",
            reply_markup=keyboard,
        )


@router.callback_query(lambda c: c.data == CallbackData.FINISH_BOOKING.value)
async def finish_booking(callback_query: types.CallbackQuery):
    user = await identity_service.get_user_by_identity(
        Platforms.TELEGRAM,
        str(callback_query.from_user.id),
    )

    if user:
        await session_service.clear_state(user.id, Platforms.TELEGRAM)

    await callback_query.message.edit_text(
        "Бронирование завершено. Возвращаем вас в главное меню."
    )

    await bot.send_message(
        callback_query.from_user.id,
        "Выберите действие:",
        reply_markup=MenuBuilder.generate_main_menu(),
    )


@router.message(Command("send_admin_message"))
async def send_admin_message(message: types.Message):
    """
    Отправляет сообщение от администратора всем активным пользователям.
    """
    if message.from_user.id != ADMIN_TELEGRAM_ID:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    if len(message.text.split(maxsplit=1)) < 2:
        await message.answer("❌ Пожалуйста, укажите сообщение после команды.\nПример: /send_admin_message Привет всем!")
        return
    admin_message = message.text.split(maxsplit=1)[1]

    session = await database.get_session()

    try:
        active_users = session.query(User).all()

        if not active_users:
            await message.answer("⚠️ Нет активных пользователей для рассылки сообщения.")
            return

        for user in active_users:
            try:
                await bot.send_message(chat_id=decrypt_telegram_id(user.telegram_id),
                                       text=f"⚠️⚠️⚠️{admin_message}⚠️⚠️⚠️")
            except Exception as exception:
                logger.error(f"Ошибка при отправке сообщения пользователю {user.telegram_id}: {exception}")

        await message.answer("✅ Сообщение успешно отправлено всем активным пользователям.")
    finally:
        await database.close_session()


async def main():
    dispatcher.include_router(router)
    logger.info('Бот запущен и готов к работе')

    await bot.delete_webhook(drop_pending_updates=True)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
