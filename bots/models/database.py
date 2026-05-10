import asyncio
import logging
import threading
import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from bots.config.logging_config import get_logger

logger = get_logger(__name__)

DATABASE_URL = "mysql+pymysql://root:@localhost/telegram_bot"


class Database:
    __instance = None
    __threading_lock = threading.Lock()
    __MAX_WAITING_CONNECT_TIME = 600
    __WAITING_CONNECT_TIME = 30

    def __new__(cls):
        with cls.__threading_lock:
            if cls.__instance is None:
                cls.__instance = super(Database, cls).__new__(cls)
                cls.__instance.__init__()

            return cls.__instance

    def __init__(self):
        if not hasattr(self, "_initialized"):  # Чтобы не инициализировать повторно
            logging.basicConfig()
            logging.getLogger("sqlalchemy.engine").setLevel(logging.DEBUG)

            self.__engine = create_engine(DATABASE_URL, echo=True, pool_recycle=1800)
            self.__session_factory = sessionmaker(autocommit=False, autoflush=False, bind=self.__engine)
            self.__session = None
            self.__initialized = True  # Флаг, что объект уже инициализирован

    async def connect(self):
        """Запуск процесса подключения к БД"""
        await self.__reconnect()

    async def get_session(self) -> Session:
        """
        Возвращает текущую сессию SQLAlchemy. Если сессия закрыта — создаем новую.
        """
        if self.__session is None or not self.__session.is_active:
            logger.info("⚠ Сессия закрыта. Создаем новую.")
            await self.__reconnect()

        return self.__session

    async def close_session(self):
        """
        Закрывает текущую сессию.
        """
        if self.__session:
            self.__session.close()
            logger.info("🔴 Сессия базы данных закрыта.")

    async def rollback(self):
        """
        Откатывает сессию в случае ошибки.
        """
        if self.__session:
            logger.warning("⏪ Откат транзакции из-за ошибки")
            self.__session.rollback()

    async def execute_with_retry(self, function, *args, **kwargs):
        """
        Выполняет переданную функцию с автоматическим повтором в случае потери соединения.
        """
        try:
            return await function(*args, **kwargs)
        except OperationalError:
            logger.warning("⚠ Потеряно соединение с БД. Переподключаемся...")
            await self.__reconnect()
            return await function(*args, **kwargs)
        except SQLAlchemyError as exception:
            await self.rollback()
            logger.error(f"❌ Ошибка при выполнении запроса: {exception}")
            return None

    async def __reconnect(self):
        """
        Попытка установить соединение с базой данных.
        Если соединение не удается, повторяем попытку каждые 30 секунд асинхронно.
        Если за 10 минут подключение не установлено, выбрасываем исключение.
        """

        start_time = time.time()
        is_database_connect = False

        while not is_database_connect:
            try:
                self.__session = self.__session_factory()
                await self.__execute('SELECT 1')
                logger.info('✅ Успешное подключение к базе данных')
                is_database_connect = True
            except OperationalError as exception:
                elapsed_time = time.time() - start_time

                if elapsed_time > self.__MAX_WAITING_CONNECT_TIME:
                    logger.error("❌ Не удалось подключиться к базе данных за 10 минут. Завершаем попытки.")
                    raise RuntimeError("Не удалось подключиться к базе данных")

                logger.warning(f"⚠ Ошибка подключения к БД: {exception}. Повторная попытка через 30 секунд...")
                await asyncio.sleep(self.__WAITING_CONNECT_TIME)

    async def __execute(self, query: str):
        """
        Выполнение SQL-запроса через `run_in_executor`.
        """

        asyncio_loop = asyncio.get_running_loop()
        return await asyncio_loop.run_in_executor(None, self.__session.execute, text(query))
