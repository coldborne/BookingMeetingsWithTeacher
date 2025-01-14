import asyncio
import logging
from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, date, timedelta
from pytz import timezone
from dateutil import tz

import consts
from calDavService import CalDavService

user_data = {}

API_TOKEN = 'YOUR_BOT_TOKEN'

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
router = Router()

calDavService = CalDavService(consts.URL, consts.USERNAME, consts.APPLE_APP_PASSWORD)


def generate_main_menu():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Бронировать событие", callback_data="book_event")],
        ]
    )
    return keyboard


@router.callback_query(lambda c: c.data == "book_event")
async def book_event(callback_query: types.CallbackQuery):
    today = date.today()
    keyboard = generate_calendar_keyboard(today.year, today.month)
    await callback_query.message.edit_text("Выберите дату:", reply_markup=keyboard)


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
        [InlineKeyboardButton(text="Закончить бронирование на этот день", callback_data="finish_booking")])

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
async def start_command(message: types.Message):
    user_data[message.from_user.id] = {
        "name": None,
        "surname": None,
        "language": None,
    }
    await message.answer("Привет! Как вас зовут?")
    await message.answer("Введите ваше имя:")


@router.message(lambda message: message.from_user.id in user_data and not user_data[message.from_user.id].get("name"))
async def process_name(message: types.Message):
    user_data[message.from_user.id]["name"] = message.text
    await message.answer("Введите вашу фамилию:")


@router.message(
    lambda message: message.from_user.id in user_data and not user_data[message.from_user.id].get("surname"))
async def process_surname(message: types.Message):
    user_data[message.from_user.id]["surname"] = message.text
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Python", callback_data="language_python"),
             InlineKeyboardButton(text="C#", callback_data="language_csharp")]
        ]
    )
    await message.answer("Выберите ваш язык программирования:", reply_markup=keyboard)


@router.callback_query(lambda c: c.data.startswith("language"))
async def process_language(callback_query: types.CallbackQuery):
    language = callback_query.data.split("_")[1]
    user_data[callback_query.from_user.id]["language"] = language
    await callback_query.message.edit_text("Добро пожаловать в систему бронирования!")
    await bot.send_message(callback_query.from_user.id, "Выберите действие:", reply_markup=generate_main_menu())


@router.callback_query(lambda c: c.data == "menu_booking")
async def menu_booking(callback_query: types.CallbackQuery):
    today = datetime.today().date()
    keyboard = generate_calendar_keyboard(today.year, today.month)
    await callback_query.message.edit_text("Выберите дату для бронирования:", reply_markup=keyboard)


@router.callback_query(lambda c: c.data.startswith("date_"))
async def select_date(callback_query: types.CallbackQuery):
    _, year, month, day = callback_query.data.split("_")
    selected_date = date(int(year), int(month), int(day))
    user_data[callback_query.from_user.id]["selected_date"] = selected_date

    await callback_query.message.edit_text(f"Вы выбрали дату: {selected_date}. Теперь выберите время.")
    busy_hours = calDavService.parse_calendar_events(calDavService.get_events_time_by_date(selected_date))
    keyboard = generate_hours_keyboard(busy_hours)
    await bot.send_message(callback_query.from_user.id, "Выберите время:", reply_markup=keyboard)


@router.callback_query(lambda c: c.data.startswith("month_"))
async def change_month(callback_query: types.CallbackQuery):
    _, year, month = callback_query.data.split("_")
    year, month = int(year), int(month)

    keyboard = generate_calendar_keyboard(year, month)
    await callback_query.message.edit_reply_markup(reply_markup=keyboard)


@router.callback_query(lambda c: c.data.startswith("time"))
async def process_time(callback_query: types.CallbackQuery):
    hour = int(callback_query.data.split("_")[1])
    user = user_data[callback_query.from_user.id]
    selected_date = user["selected_date"]

    utc = timezone("UTC")
    local_tz = timezone("Europe/Moscow")

    local_start = local_tz.localize(datetime(selected_date.year, selected_date.month, selected_date.day, hour, 0))
    local_end = local_start + timedelta(hours=1)

    start_time = local_start.astimezone(utc)
    end_time = local_end.astimezone(utc)

    success = await calDavService.book_slot(f"{user['name']} {user['surname']} {user['language']}", start_time,
                                            end_time)

    if success:
        await bot.send_message(callback_query.from_user.id, "Событие успешно создано!")
    else:
        await bot.send_message(callback_query.from_user.id, "Не удалось создать событие. Слот занят.")

    busy_hours = calDavService.parse_calendar_events(calDavService.get_events_time_by_date(selected_date))
    new_keyboard = generate_hours_keyboard(busy_hours)
    await callback_query.message.edit_reply_markup(reply_markup=new_keyboard)


@router.callback_query(lambda c: c.data == "finish_booking")
async def finish_booking(callback_query: types.CallbackQuery):
    user = user_data[callback_query.from_user.id]
    selected_date = user["selected_date"]

    await callback_query.message.delete()

    await bot.send_message(callback_query.from_user.id, f"Бронирование на {selected_date} завершено.")
    await bot.send_message(callback_query.from_user.id, "Выберите действие:", reply_markup=generate_main_menu())


async def main():
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
