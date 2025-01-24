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


class UserDataHandler:
    """
    Класс для проверки, заполнения и обновления данных пользователя.
    """

    def __init__(self, user_service: UserService, telegram_id: int):
        self.user_service = user_service
        self.telegram_id = telegram_id
        self.user = user_service.get_user_by_telegram_id(telegram_id)

    def ensure_user_exists(self):
        """
        Убеждается, что пользователь существует в базе данных. Если нет — создает нового.
        """
        if not self.user:
            logger.info(f"Создаём нового пользователя для Telegram ID: {self.telegram_id}")
            self.user = self.user_service.create_user(self.telegram_id)

    def get_missing_data_state(self) -> State | None:
        """
        Возвращает состояние для недостающих данных пользователя. Если данные полные, возвращает None.
        """
        if not self.user.name:
            return UserDataStates.waiting_for_name
        if not self.user.surname:
            return UserDataStates.waiting_for_surname
        if not self.user.language:
            return UserDataStates.waiting_for_language
        return None

    def update_user_data(self, **kwargs):
        """
        Обновляет данные пользователя в базе данных.
        """
        self.user_service.update_user(self.telegram_id, **kwargs)
        logger.info(f"Данные пользователя Telegram ID: {self.telegram_id} успешно обновлены.")
