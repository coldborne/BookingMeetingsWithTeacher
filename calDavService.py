import caldav
import uuid

from datetime import datetime, date
from icalendar import Calendar, Event
from typing import Set
from pytz import timezone

from consts import WORK_CALENDAR, STUDENT_WORK_CALENDAR


class CalDavService:
    def __init__(self, url: str, username: str, app_password: str):
        self.__url = url
        self.__username = username
        self.__app_password = app_password

        self.__client = caldav.DAVClient(self.__url, username=self.__username, password=self.__app_password)
        self.__principal = self.__client.principal()
        self.__principal.calendars()
        self.__calendars = self.__get_calendars()

    def get_events(self, start_datetime: datetime, end_datetime: datetime) -> list:
        work_calendar = self.__calendars['work']
        student_work_calendar = self.__calendars['student_work']

        events = []

        try:
            events += work_calendar.date_search(start=start_datetime, end=end_datetime)
            events += student_work_calendar.date_search(start=start_datetime, end=end_datetime)
        except Exception as e:
            print(f"Ошибка при получении событий: {e}")

        return events

    def get_events_time_by_date(self, target_date: date) -> list:
        local_tz = timezone("Europe/Moscow")
        utc = timezone("UTC")

        start_datetime = local_tz.localize(datetime.combine(target_date, datetime.min.time())).astimezone(utc)
        end_datetime = local_tz.localize(datetime.combine(target_date, datetime.max.time())).astimezone(utc)

        return self.get_events(start_datetime, end_datetime)

    async def book_slot(self, summary, start, end, description=None):
        """
        Создает событие в календаре с использованием библиотеки caldav.

        Args:
            summary: Название события.
            start: Время начала (datetime, UTC).
            end: Время окончания (datetime, UTC).
            description: Описание события (по умолчанию None).

        Returns:
            bool: True, если событие успешно создано, иначе False.
        """
        try:
            local_tz = timezone("Europe/Moscow")

            local_start = start.astimezone(local_tz)
            local_end = end.astimezone(local_tz)

            work_calendar = self.__calendars['work']
            student_work_calendar = self.__calendars['student_work']

            events = self.get_events(start, end)

            for event in events:
                event_data = Calendar.from_ical(event.data)

                for component in event_data.walk("VEVENT"):
                    existing_start = component.get("DTSTART").dt
                    existing_end = component.get("DTEND").dt

                    if isinstance(existing_start, datetime) and isinstance(existing_end, datetime):
                        existing_start = existing_start.astimezone(local_tz)
                        existing_end = existing_end.astimezone(local_tz)

                    if existing_start < local_end and existing_end > local_start:
                        return False

            event = Event()
            event.add("summary", summary)
            event.add("dtstart", local_start)
            event.add("dtend", local_end)
            event.add("uid", str(uuid.uuid4()))

            if description:
                event.add("description", description)

            calendar_data = Calendar()
            calendar_data.add_component(event)

            student_work_calendar.add_event(calendar_data.to_ical())
            return True
        except Exception as e:
            print(f"Ошибка при создании события: {e}")
            return False

    '''def print_events(self):
        # Определяем временной диапазон

        utc = timezone("UTC")
        local_tz = timezone("Europe/Moscow")  # Пример временной зоны

        start_date = utc.localize(datetime.now()).astimezone(local_tz)
        end_date = utc.localize(datetime.now() + timedelta(days=5)).astimezone(local_tz)

        # Поиск событий в указанном диапазоне
        events = calendar.date_search(start=start_date, end=end_date)

        if not events:
            print("События не найдены.")
        else:
            for event in events:
                # Получение данных события
                event_data = event.data
                print(event)
                print('-------------------------')
                print(event_data)
                print('-------------------------')

                # Альтернативно, вы можете использовать библиотеку `icalendar` для разбора iCalendar данных
                from icalendar import Calendar

                parsed_event = Calendar.from_ical(event_data)
                for component in parsed_event.walk('VEVENT'):
                    print("Событие:")
                    print(f"  Название: {component.get('SUMMARY')}")
                    print(f"  Начало: {component.get('DTSTART').dt}")
                    print(f"  Конец: {component.get('DTEND').dt}")
                    print(f"  Описание: {component.get('DESCRIPTION')}\n")

                print('-------------------------')
    '''

    def parse_calendar_events(self, events: list) -> Set[int]:
        busy_hours = set()

        for event in events:
            try:
                parsed_event = Calendar.from_ical(event.data)
                for component in parsed_event.walk('VEVENT'):
                    start = component.get('DTSTART').dt
                    end = component.get('DTEND').dt

                    if isinstance(start, datetime) and isinstance(end, datetime):
                        busy_hours.update(range(start.hour, end.hour))
            except Exception as e:
                print(f"Ошибка при парсинге события: {e}")

        return busy_hours

    def __get_calendars(self) -> dict[str, caldav.Calendar]:
        calendars = dict()

        calendars['work'] = self.__principal.calendar(name=WORK_CALENDAR.get_name(),
                                                      cal_id=WORK_CALENDAR.get_id(),
                                                      cal_url=WORK_CALENDAR.get_url())
        calendars['student_work'] = self.__principal.calendar(name=STUDENT_WORK_CALENDAR.get_name(),
                                                              cal_id=STUDENT_WORK_CALENDAR.get_id(),
                                                              cal_url=STUDENT_WORK_CALENDAR.get_url())

        return calendars
