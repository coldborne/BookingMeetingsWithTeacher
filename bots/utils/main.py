from datetime import date, timedelta

from bots.handlers.telegram_bot import availability_days_config


async def is_date_available(selected_date: date, today: date):
    start_available_date = today + timedelta(days=1)
    end_available_date = start_available_date + timedelta(days=30)

    return start_available_date <= selected_date <= end_available_date and not availability_days_config.is_date_blocked(
        selected_date)
