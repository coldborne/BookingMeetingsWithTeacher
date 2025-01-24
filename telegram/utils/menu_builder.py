from calendar import monthrange
from datetime import date
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.utils.callback_data import CallbackData


class MenuBuilder:
    """
    Создаёт элементы меню и клавиатуры.
    """
    __BOOK_EVENT_TEXT = "Бронировать событие"
    __UPDATE_DATA_TEXT = "Изменить данные"
    __FINISH_BOOKING_TEXT = "Закончить бронирование на этот день"
    __BACK_BUTTON_TEXT = "⬅️"
    __FORWARD_BUTTON_TEXT = "➡️"
    __DATE_FORMAT_TEXT = "{year}-{month:02}"
    __WEEK_DAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

    __AVAILABLE_SYMBOL = "🟢"
    __BUSY_SYMBOL = "🔴"

    __START_DAY_HOUR = 10
    __END_DAY_HOUR = 18
    __PER_ROW_BUTTONS_COUNT = 4

    __IN_WEEK_DAYS_COUNT = 7
    __FIRST_MONTH_NUMBER = 1
    __LAST_MONTH_NUMBER = 12

    @staticmethod
    def generate_main_menu() -> InlineKeyboardMarkup:
        """Создаёт главное меню."""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=MenuBuilder.__BOOK_EVENT_TEXT, callback_data=CallbackData.BOOK_EVENT.value)],
                [InlineKeyboardButton(text=MenuBuilder.__UPDATE_DATA_TEXT,
                                      callback_data=CallbackData.UPDATE_DATA.value)],
            ]
        )

    @staticmethod
    def generate_language_keyboard() -> InlineKeyboardMarkup:
        """Создаёт клавиатуру для выбора языка программирования."""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="Python", callback_data=CallbackData.LANGUAGE_PYTHON.value),
                    InlineKeyboardButton(text="C#", callback_data=CallbackData.LANGUAGE_CSHARP.value),
                ],
            ]
        )

    @staticmethod
    def generate_hours_keyboard(events: list[int]) -> InlineKeyboardMarkup:
        """Создаёт клавиатуру для выбора времени."""
        hours = range(MenuBuilder.__START_DAY_HOUR, MenuBuilder.__END_DAY_HOUR)
        buttons = []

        for hour in hours:
            time_str = f"{hour}:00"
            is_available = hour not in events
            button_text = f"{MenuBuilder.__AVAILABLE_SYMBOL} {time_str}" if is_available else f"{MenuBuilder.__BUSY_SYMBOL} {time_str}"
            callback_data = CallbackData.time(hour) if is_available else CallbackData.IGNORE.value
            buttons.append(InlineKeyboardButton(text=button_text, callback_data=callback_data))

        inline_keyboard = [buttons[i:i + MenuBuilder.__PER_ROW_BUTTONS_COUNT] for i in
                           range(0, len(buttons), MenuBuilder.__PER_ROW_BUTTONS_COUNT)]

        inline_keyboard.append(
            [InlineKeyboardButton(text=MenuBuilder.__FINISH_BOOKING_TEXT,
                                  callback_data=CallbackData.FINISH_BOOKING.value)]
        )

        return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

    @staticmethod
    def generate_calendar_keyboard(year: int, month: int) -> InlineKeyboardMarkup:
        """Создаёт календарь для выбора даты."""
        inline_keyboard = [[InlineKeyboardButton(text=day, callback_data=CallbackData.IGNORE.value) for day in
                            MenuBuilder.__WEEK_DAYS]]

        _, days_in_month = monthrange(year, month)
        first_day = date(year, month, 1).weekday()

        buttons = [InlineKeyboardButton(text=" ", callback_data=CallbackData.IGNORE.value)] * first_day

        for day in range(1, days_in_month + 1):
            buttons.append(
                InlineKeyboardButton(text=str(day), callback_data=CallbackData.date(year, month, day))
            )

        for row_number in range(0, len(buttons), len(MenuBuilder.__WEEK_DAYS)):
            inline_keyboard.append(buttons[row_number:row_number + len(MenuBuilder.__WEEK_DAYS)])

        previous_month, previous_year = (month - 1, year) if month > MenuBuilder.__FIRST_MONTH_NUMBER else (
            MenuBuilder.__LAST_MONTH_NUMBER, year - 1)

        next_month, next_year = (month + 1, year) if month < MenuBuilder.__LAST_MONTH_NUMBER else (
            MenuBuilder.__FIRST_MONTH_NUMBER, year + 1)

        inline_keyboard.append([
            InlineKeyboardButton(text=MenuBuilder.__BACK_BUTTON_TEXT,
                                 callback_data=CallbackData.month(previous_year, previous_month)),
            InlineKeyboardButton(text=MenuBuilder.__DATE_FORMAT_TEXT.format(year=year, month=month),
                                 callback_data=CallbackData.IGNORE.value),
            InlineKeyboardButton(text=MenuBuilder.__FORWARD_BUTTON_TEXT,
                                 callback_data=CallbackData.month(next_year, next_month)),
        ])

        return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
