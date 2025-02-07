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

    async def get_missing_data_state(self) -> tuple[State | None, list[str], str | None]:
        """
        Возвращает состояние для недостающих данных пользователя, их список и первую необходимую характеристику.
        """
        await self.load_user()

        if not self.user:
            return UserDataStates.waiting_for_name, ["Имя", "Фамилия", "Язык"], "Имя"

        # Словарь с маппингом полей на состояния и их имена
        required_fields = {
            "name": ("Имя", UserDataStates.waiting_for_name),
            "surname": ("Фамилия", UserDataStates.waiting_for_surname),
            "language": ("Язык", UserDataStates.waiting_for_language),
        }

        missing_fields = [label for field, (label, _) in required_fields.items() if not getattr(self.user, field)]
        first_missing_state = next(
            ((state, label) for field, (label, state) in required_fields.items() if not getattr(self.user, field)),
            (None, None)
        )

        return first_missing_state[0], missing_fields, first_missing_state[1]

    async def update_user_data(self, **kwargs):
        """
        Обновляет данные пользователя в базе данных.
        """
        await self.user_service.update_user(self.telegram_id, **kwargs)
        await self.load_user()  # Обновляем локальный объект user
        logger.info(f"Данные пользователя Telegram ID: {self.telegram_id} успешно обновлены.")
