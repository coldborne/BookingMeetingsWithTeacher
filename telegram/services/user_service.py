import hashlib
from sqlalchemy.exc import IntegrityError

from telegram.config.logging_config import get_logger
from telegram.models.database import Database
from telegram.models.models import User, UserDTO

logger = get_logger(__name__)


class UserService:
    def __init__(self, database: Database, secret_salt: str):
        """
        Инициализирует UserService, используя единственный экземпляр Database.
        """
        self.__database = database
        self.__salt = secret_salt

    def hash_telegram_id(self, telegram_id: int) -> str:
        """
        Хэширует telegram_id с использованием секретной "соли".
        """
        hash_input = f"{telegram_id}{self.__salt}".encode('utf-8')
        return hashlib.sha256(hash_input).hexdigest()

    def __to_dto(self, user: User, original_telegram_id: int) -> UserDTO | None:
        """
        Преобразует SQLAlchemy-модель в DTO с оригинальным telegram_id.
        """
        if user:
            return UserDTO(
                telegram_id=original_telegram_id,
                name=user.name,
                surname=user.surname,
                language=user.language,
                state=user.state
            )

        return None

    async def get_user_by_telegram_id(self, telegram_id: int) -> UserDTO:
        """
        Получает пользователя из базы данных и возвращает его как DTO.
        """
        session = await self.__database.get_session()

        try:
            hashed_id = self.hash_telegram_id(telegram_id)
            user = session.query(User).filter(User.telegram_id == hashed_id).first()
            return self.__to_dto(user, telegram_id)
        finally:
            await self.__database.close_session()

    async def create_user(self, telegram_id: int) -> UserDTO | None:
        """
        Создает нового пользователя в базе данных и возвращает его как DTO.
        """
        session = await self.__database.get_session()
        hashed_id = None

        try:
            hashed_id = self.hash_telegram_id(telegram_id)
            user = User(telegram_id=hashed_id)
            session.add(user)
            session.commit()
            session.refresh(user)
            return self.__to_dto(user, telegram_id)
        except IntegrityError:
            session.rollback()
            logger.warning(f"Пользователь с telegram_id={hashed_id} уже существует")
            return None
        finally:
            await self.__database.close_session()

    async def update_user(self, telegram_id: int, **kwargs):
        """
        Обновляет пользователя в базе данных.
        """
        session = await self.__database.get_session()

        try:
            hashed_id = self.hash_telegram_id(telegram_id)
            user = session.query(User).filter(User.telegram_id == hashed_id).first()

            if user:
                for key, value in kwargs.items():
                    setattr(user, key, value)

                session.commit()
                session.refresh(user)
                return self.__to_dto(user, telegram_id)
            else:
                logger.warning(f"Пользователь с telegram_id={hashed_id} не найден для обновления")
                return None
        finally:
            await self.__database.close_session()

    async def get_user_state(self, telegram_id: int) -> str:
        """
        Получает состояние пользователя из базы данных.
        """
        session = await self.__database.get_session()

        try:
            hashed_id = self.hash_telegram_id(telegram_id)
            user = session.query(User).filter(User.telegram_id == hashed_id).first()
            return user.state if user else None
        finally:
            await self.__database.close_session()

    async def set_user_state(self, telegram_id: int, state: str):
        """
        Устанавливает состояние пользователя в базе данных.
        """
        await self.update_user(telegram_id, state=state)
