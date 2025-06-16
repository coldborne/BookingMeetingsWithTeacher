from aiogram.fsm.state import StatesGroup, State

from telegram.config.logging_config import get_logger
from telegram.services.user_service import UserService

logger = get_logger(__name__)


class UserDataStates(StatesGroup):
    """
        Состояния для многошагового ввода данных пользователя.
    """
    WAITING_FOR_NAME = State()
    WAITING_FOR_SURNAME = State()
    WAITING_FOR_LANGUAGE = State()
    CONFIRMING_CHANGES = State()


class UserDataHandler:
    """
    Класс для проверки, заполнения и обновления данных пользователя.
    """

    def __init__(self, user_service: UserService, telegram_id: int):
        self.__user_service = user_service
        self.__telegram_id = telegram_id
        self.__user = None

    async def ensure_user_exists(self):
        """
        Убеждается, что пользователь существует в базе данных. Если нет — создает нового.
        """
        await self.__load_user()

        if not self.__user:
            logger.info(f"Создаём нового пользователя для Telegram ID: {self.__telegram_id}")
            self.__user = await self.__user_service.create_user(self.__telegram_id)

    async def get_missing_data_state(self) -> tuple[State | None, list[str], str | None]:
        """
        Возвращает состояние для недостающих данных пользователя, их список и первую необходимую характеристику.
        """
        await self.__load_user()

        if not self.__user:
            return UserDataStates.WAITING_FOR_NAME, ["Имя", "Фамилия", "Язык"], "Имя"

        # Словарь с маппингом полей на состояния и их имена
        required_fields = {
            "name": ("Имя", UserDataStates.WAITING_FOR_NAME),
            "surname": ("Фамилия", UserDataStates.WAITING_FOR_SURNAME),
            "language": ("Язык", UserDataStates.WAITING_FOR_LANGUAGE),
        }

        missing_fields = [label for field, (label, _) in required_fields.items() if not getattr(self.__user, field)]
        first_missing_state = next(
            ((state, label) for field, (label, state) in required_fields.items() if not getattr(self.__user, field)),
            (None, None)
        )

        return first_missing_state[0], missing_fields, first_missing_state[1]

    async def update_user_data(self, **kwargs):
        """
        Обновляет данные пользователя в базе данных.
        """
        await self.__user_service.update_user(self.__telegram_id, **kwargs)
        await self.__load_user()

        logger.info(f"Данные пользователя Telegram ID: {self.__telegram_id} успешно обновлены.")

    async def __load_user(self):
        """
        Загружает пользователя из базы данных и сохраняет в self.user.
        """
        self.__user = await self.__user_service.get_user_by_telegram_id(self.__telegram_id)
