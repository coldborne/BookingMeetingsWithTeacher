import logging
import hashlib
from sqlalchemy.orm import Session
from models import User, UserDTO

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, database: Session, secret_salt: str):
        self.__database = database
        self.__salt = secret_salt

    def hash_telegram_id(self, telegram_id: int) -> str:
        """
        Хэширует telegram_id с использованием секретной "соли".
        """
        hash_input = f"{telegram_id}{self.__salt}".encode('utf-8')
        return hashlib.sha256(hash_input).hexdigest()

    def __to_dto(self, user: User, original_telegram_id: int) -> UserDTO:
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

    def get_user_by_telegram_id(self, telegram_id: int) -> UserDTO:
        """
        Получает пользователя из базы данных и возвращает его как DTO.
        """
        hashed_id = self.hash_telegram_id(telegram_id)
        user = self.__database.query(User).filter(User.telegram_id == hashed_id).first()
        return self.__to_dto(user, telegram_id)

    def create_user(self, telegram_id: int) -> UserDTO:
        """
        Создает нового пользователя в базе данных и возвращает его как DTO.
        """
        hashed_id = self.hash_telegram_id(telegram_id)
        user = User(telegram_id=hashed_id)
        self.__database.add(user)
        self.__database.commit()
        self.__database.refresh(user)
        return self.__to_dto(user, telegram_id)

    def update_user(self, telegram_id: int, **kwargs):
        """
        Обновляет пользователя в базе данных.
        """
        hashed_id = self.hash_telegram_id(telegram_id)
        user = self.__database.query(User).filter(User.telegram_id == hashed_id).first()

        if user:
            for key, value in kwargs.items():
                setattr(user, key, value)

            self.__database.commit()
            self.__database.refresh(user)
            return self.__to_dto(user, telegram_id)
        else:
            logger.warning(f"Пользователь с telegram_id={hashed_id} не найден для обновления")
            return None

    def get_user_state(self, telegram_id: int) -> str:
        """
        Получает состояние пользователя из базы данных.
        """
        hashed_id = self.hash_telegram_id(telegram_id)
        user = self.__database.query(User).filter(User.telegram_id == hashed_id).first()
        return user.state if user else None

    def set_user_state(self, telegram_id: int, state: str):
        """
        Устанавливает состояние пользователя в базе данных.
        """
        self.update_user(telegram_id, state=state)
