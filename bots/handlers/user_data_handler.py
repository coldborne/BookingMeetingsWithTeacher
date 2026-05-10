from aiogram.fsm.state import State, StatesGroup

from bots.config.logging_config import get_logger
from bots.services.user_service import UserService

logger = get_logger(__name__)


class UserDataStates(StatesGroup):
    WAITING_FOR_NAME = State()
    WAITING_FOR_SURNAME = State()
    WAITING_FOR_LANGUAGE = State()
    CONFIRMING_CHANGES = State()


class UserDataHandler:
    def __init__(self, user_service: UserService, user_id: int):
        self.__user_service = user_service
        self.__user_id = user_id
        self.__user = None

    async def ensure_user_exists(self):
        await self.__load_user()

        if not self.__user:
            logger.warning(f"Пользователь id={self.__user_id} не найден")

    async def get_missing_data_state(self) -> tuple[State | None, list[str], str | None]:
        await self.__load_user()

        if not self.__user:
            return UserDataStates.WAITING_FOR_NAME, ["Имя", "Фамилия", "Язык"], "Имя"

        required_fields = {
            "name": ("Имя", UserDataStates.WAITING_FOR_NAME),
            "surname": ("Фамилия", UserDataStates.WAITING_FOR_SURNAME),
            "language": ("Язык", UserDataStates.WAITING_FOR_LANGUAGE),
        }

        missing_fields = [
            label for field, (label, _) in required_fields.items() if not getattr(self.__user, field)
        ]

        first_missing_state = next(
            (
                (state, label)
                for field, (label, state) in required_fields.items()
                if not getattr(self.__user, field)
            ),
            (None, None),
        )

        return first_missing_state[0], missing_fields, first_missing_state[1]

    async def update_user_data(self, **kwargs):
        await self.__user_service.update_user_by_id(self.__user_id, **kwargs)
        await self.__load_user()
        logger.info(f"Данные пользователя id={self.__user_id} успешно обновлены.")

    async def __load_user(self):
        self.__user = await self.__user_service.get_user_by_id(self.__user_id)