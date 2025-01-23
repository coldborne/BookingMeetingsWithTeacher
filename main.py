import asyncio
from telegram.config.logging_config import get_logger
from telegram.handlers.telegram_bot import main as start_telegram_bot

logger = get_logger(__name__)


async def start_application():
    """
    Главная точка запуска приложения.
    """

    logger.info("Запуск приложения...")

    try:
        await start_telegram_bot()
    except Exception as exeption:
        logger.error(f"Ошибка в приложении: {exeption}")
    finally:
        logger.info("Приложение завершено.")


if __name__ == "__main__":
    asyncio.run(start_application())
