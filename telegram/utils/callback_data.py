from enum import Enum


class CallbackData(Enum):
    """Класс, хранящий callback_data для клавиатур."""
    BOOK_EVENT = "book_event"
    UPDATE_DATA = "update_data"
    LANGUAGE_PYTHON = "language_python"
    LANGUAGE_CSHARP = "language_csharp"
    FINISH_BOOKING = "finish_booking"
    IGNORE = "ignore"
    TIME_PREFIX = "time_"
    DATE_PREFIX = "date_"
    MONTH_PREFIX = "month_"

    @staticmethod
    def time(hour: int) -> str:
        return f"{CallbackData.TIME_PREFIX.value}{hour}"

    @staticmethod
    def date(year: int, month: int, day: int) -> str:
        return f"{CallbackData.DATE_PREFIX.value}{year}_{month}_{day}"

    @staticmethod
    def month(year: int, month: int) -> str:
        return f"{CallbackData.MONTH_PREFIX.value}{year}_{month}"
