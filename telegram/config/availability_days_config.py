from datetime import date
from enum import Enum


class Weekday(Enum):
    """
    Enum для представления дней недели.
    """
    MONDAY = 1
    TUESDAY = 2
    WEDNESDAY = 3
    THURSDAY = 4
    FRIDAY = 5
    SATURDAY = 6
    SUNDAY = 7


class AvailabilityDaysConfig:
    """
    Класс для управления доступностью дней для бронирования.
    """

    def __init__(self):
        self.blocked_weekdays = {Weekday.SUNDAY}
        self.blocked_dates = set()

    def is_date_blocked(self, target_date: date) -> bool:
        """
        Проверяет, является ли дата недоступной для бронирования.

        :param target_date: Дата для проверки.
        :return: True, если дата недоступна, иначе False.
        """
        return (
                Weekday(target_date.weekday() + 1) in self.blocked_weekdays or
                target_date in self.blocked_dates
        )

    def add_blocked_date(self, blocked_date: date):
        """
        Добавляет конкретную дату в список запрещённых.

        :param blocked_date: Дата для добавления.
        """
        self.blocked_dates.add(blocked_date)

    def remove_blocked_date(self, blocked_date: date):
        """
        Убирает дату из списка запрещённых.

        :param blocked_date: Дата для удаления.
        """
        self.blocked_dates.discard(blocked_date)

    def set_blocked_weekdays(self, weekdays: set[Weekday]):
        """
        Задаёт дни недели, для которых бронирование запрещено.

        :param weekdays: Множество дней недели (Weekday Enum).
        """
        self.blocked_weekdays = weekdays
