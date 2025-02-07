from aiogram.fsm.state import StatesGroup, State

from telegram.config.logging_config import get_logger
from telegram.services.user_service import UserService

logger = get_logger(__name__)


class UserDataStates(StatesGroup):
    """
        Состояния для многошагового ввода данных пользователя.
    """
    waiting_for_name = State()
    waiting_for_surname = State()
    waiting_for_language = State()
    confirming_changes = State()


class UserDataHandler:
    """
    Класс для проверки, заполнения и обновления данных пользователя.
    """

    def __init__(self, user_service: UserService, telegram_id: int):
        self.user_service = user_service
        self.telegram_id = telegram_id
        self.user = None  # Теперь user загружается асинхронно

    async def load_user(self):
        """
        Загружает пользователя из базы данных и сохраняет в self.user.
        """
        self.user = await self.user_service.get_user_by_telegram_id(self.telegram_id)

    async def ensure_user_exists(self):
        """
        Убеждается, что пользователь существует в базе данных. Если нет — создает нового.
        """
        await self.load_user()

        if not self.user:
            logger.info(f"Создаём нового пользователя для Telegram ID: {self.telegram_id}")
            self.user = await self.user_service.create_user(self.telegram_id)

    async def get_missing_data_state(self) -> State | None:
        """
        Возвращает состояние для недостающих данных пользователя. Если данные полные, возвращает None.
        """
        await self.load_user()

        if not self.user:
            return UserDataStates.waiting_for_name  # На случай, если пользователь не загрузился

        if not self.user.name:
            return UserDataStates.waiting_for_name
        if not self.user.surname:
            return UserDataStates.waiting_for_surname
        if not self.user.language:
            return UserDataStates.waiting_for_language
        return None

    async def update_user_data(self, **kwargs):
        """
        Обновляет данные пользователя в базе данных.
        """
        await self.user_service.update_user(self.telegram_id, **kwargs)
        await self.load_user()  # Обновляем локальный объект user
        logger.info(f"Данные пользователя Telegram ID: {self.telegram_id} успешно обновлены.")
